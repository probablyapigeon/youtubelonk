"""Read-only YouTube chat intake. Network thread queues; main thread simulates."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import random
import re
import tempfile
import threading
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


ERROR_HELP = {
    'API_KEY_SERVICE_BLOCKED': 'Edit this key in Google Cloud Credentials; allow YouTube Data API v3 under API restrictions.',
    'SERVICE_DISABLED': 'Enable YouTube Data API v3 in the project that owns this key.',
    'API_KEY_HTTP_REFERRER_BLOCKED': 'This key is restricted to websites; configure a key for the desktop bridge.',
    'API_KEY_IP_ADDRESS_BLOCKED': 'This key does not allow this computer in its IP restrictions.',
    'API_KEY_INVALID': 'Run /youtube setup with the current key.',
    'API_KEY_EXPIRED': 'Run /youtube setup with a current key.',
    'ACCESS_DENIED': 'Google denied YouTube service access; check this key and its owning project.',
}


def settings_directory():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.config')/'LonkWorld'


def video_id(value):
    value = value.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    url = urlparse(value)
    host = (url.hostname or '').lower()
    parts = url.path.strip('/').split('/')
    result = None
    if url.scheme == 'https' and host == 'youtu.be':
        result = parts[0]
    elif url.scheme == 'https' and host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'studio.youtube.com'):
        if parts[0] == 'watch':
            result = parse_qs(url.query).get('v', [None])[0]
        elif len(parts) >= 2 and parts[0] in ('live', 'video', 'shorts'):
            result = parts[1]
    if not result or not re.fullmatch(r'[A-Za-z0-9_-]{11}', result):
        raise ValueError('Use a YouTube watch/live/Studio URL or its 11-character video ID.')
    return result


def clean_text(value, limit):
    if not isinstance(value, str):
        return ''
    value = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', value)
    value = ''.join(c if c.isspace() else '' if unicodedata.category(c) in ('Cc', 'Cs') else c for c in value)
    return ' '.join(value.split())[:limit]


def _atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class YouTubeError(Exception):
    def __init__(self, reason, retryable=False):
        self.reason, self.retryable = reason, retryable
        super().__init__(reason)


class YouTubeAPI:
    """Only two GET endpoints; never posts to YouTube or invokes a model."""
    def __init__(self, key, opener=urlopen):
        self.key, self.opener = key, opener

    def _get(self, resource, **parameters):
        parameters['key'] = self.key
        request = Request('https://www.googleapis.com/youtube/v3/'+resource+'?'+urlencode(parameters),
                          headers={'Accept': 'application/json', 'User-Agent': 'LonkWorld-Chat/1.0'})
        try:
            with self.opener(request, timeout=10) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise YouTubeError('responseTooLarge')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise YouTubeError('invalidResponse', True)
            return data
        except HTTPError as exc:
            # HTTPError's URL includes the key. Never propagate it or the raw
            # Google error text into console logs, saves or exception chains.
            reason = 'http'+str(exc.code)
            try:
                payload = json.loads(exc.read(65536))
                candidate = payload['error']['errors'][0]['reason']
                known = {'forbidden', 'liveChatDisabled', 'liveChatEnded', 'liveChatNotFound',
                         'rateLimitExceeded', 'backendError', 'quotaExceeded', 'dailyLimitExceeded',
                         'keyInvalid', 'accessNotConfigured', 'ipRefererBlocked', 'invalidPageToken',
                         'badRequest', 'invalidParameter', 'insufficientPermissions'}
                if isinstance(candidate, str) and candidate in known:
                    reason = candidate
                details = payload['error'].get('details', [])
                if isinstance(details, list):
                    for detail in details:
                        if (isinstance(detail, dict) and detail.get('@type') == 'type.googleapis.com/google.rpc.ErrorInfo'
                                and detail.get('reason') in ERROR_HELP):
                            reason = detail['reason']
                            break
            except (ValueError, KeyError, IndexError, TypeError):
                pass
            retryable = exc.code in (408, 429) or exc.code >= 500 or reason in ('rateLimitExceeded', 'backendError')
            raise YouTubeError(reason, retryable) from None
        except (URLError, TimeoutError, OSError):
            raise YouTubeError('networkInterrupted', True) from None
        except (ValueError, UnicodeError):
            raise YouTubeError('invalidResponse', True) from None

    def resolve_chat(self, identifier):
        data = self._get('videos', part='liveStreamingDetails', id=identifier)
        items = data.get('items', [])
        if not items:
            raise YouTubeError('videoUnavailableOrPrivate')
        details = items[0].get('liveStreamingDetails', {})
        if details.get('actualEndTime'):
            raise YouTubeError('liveChatEnded')
        chat = details.get('activeLiveChatId')
        if not chat:
            raise YouTubeError('waitingForLiveChat', True)
        return chat

    def messages(self, chat_id, token=None):
        parameters = {'liveChatId': chat_id, 'part': 'snippet,authorDetails', 'maxResults': 200}
        if token:
            parameters['pageToken'] = token
        return self._get('liveChat/messages', **parameters)


@dataclass(frozen=True)
class ChatMessage:
    identifier: str
    author_id: str
    author: str
    command: str
    target: str
    body: str
    received: float


class YouTubeBridge:
    QUEUE_LIMIT = 32
    MESSAGE_TTL = 60
    AUTHOR_COOLDOWN = 10
    WORLD_COOLDOWN = 2

    def __init__(self, directory=None, api_factory=YouTubeAPI, clock=time.monotonic, wall_clock=time.time):
        self.directory = Path(directory) if directory is not None else settings_directory()
        self.config_path = self.directory/'youtube.json'
        self.credentials_path = self.directory/'youtube_credentials.json'
        self.api_factory, self.clock, self.wall_clock = api_factory, clock, wall_clock
        self.settings = {'video_id': '', 'mode': 'commands', 'poll_seconds': 15}
        try:
            saved = json.loads(self.config_path.read_text(encoding='utf-8'))
            if saved.get('video_id'):
                self.settings['video_id'] = video_id(saved['video_id'])
            if saved.get('mode') in ('commands', 'all'):
                self.settings['mode'] = saved['mode']
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        self.messages_queue = queue.Queue(maxsize=self.QUEUE_LIMIT)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.state, self.error = 'disconnected', ''
        self.received = self.processed = self.dropped = 0
        self.skips = {'cooldown': 0, 'expired': 0, 'queue': 0, 'target': 0}
        self.seen, self.seen_order = set(), deque()
        self.authors = {}
        self.fresh_after = self.wall_clock()
        self.last_processed = float('-inf')
        self.notice = None

    def _key(self):
        key = os.environ.get('YOUTUBE_API_KEY', '').strip()
        if not key:
            try:
                key = json.loads(self.credentials_path.read_text(encoding='utf-8')).get('api_key', '')
            except (OSError, ValueError, AttributeError):
                return ''
        return key if isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key) else ''

    def setup(self, key):
        key = key.strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key):
            raise ValueError('That does not look like an API key. Use /youtube setup to try again.')
        _atomic_json(self.credentials_path, {'api_key': key})
        return 'YouTube key saved locally. Use /youtube reconnect.'

    def remember_stream(self, value):
        identifier = video_id(value)
        self.settings['video_id'] = identifier
        _atomic_json(self.config_path, self.settings)
        return identifier

    def _state(self, value, error=''):
        with self.lock:
            if (value, error) != (self.state, self.error):
                self.state, self.error = value, error
                self.notice = 'YouTube '+value+(': '+error if error else '')

    def _clear_queue(self):
        while True:
            try:
                self.messages_queue.get_nowait()
            except queue.Empty:
                return

    def disconnect(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=11)
            if self.thread.is_alive():
                raise ValueError('YouTube request is still stopping; try disconnect again shortly.')
        self.thread = None
        self._clear_queue()
        self._state('disconnected')
        return 'YouTube disconnected. Queued chat cleared.'

    def close(self):
        """Do not hold game shutdown hostage to an in-flight HTTP request."""
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.25)
        self._clear_queue()

    def connect(self, value=None):
        identifier = video_id(value) if value else self.settings['video_id']
        if not identifier:
            raise ValueError('Use /youtube connect STREAM_URL first.')
        self.disconnect()
        self.remember_stream(identifier)
        key = self._key()
        if not key:
            raise ValueError('Stream remembered. Run /youtube setup once to enter your YouTube Data API key privately.')
        self.stop_event = threading.Event()
        self.fresh_after = self.wall_clock()
        self.seen.clear(); self.seen_order.clear(); self.authors.clear()
        self.last_processed = float('-inf')
        self._state('connecting')
        self.thread = threading.Thread(target=self._run, args=(self.api_factory(key), identifier),
                                       name='lonk-youtube-reader', daemon=True)
        self.thread.start()
        return 'YouTube connecting. New chat enters on ticks; /youtube status shows progress.'

    def _run(self, api, identifier):
        chat, token, primed, attempts = None, None, False, 0
        interval = self.settings['poll_seconds']
        try:
            while not self.stop_event.is_set():
                try:
                    if chat is None:
                        chat = api.resolve_chat(identifier)
                    if self.stop_event.is_set():
                        break
                    page = api.messages(chat, token)
                    if self.stop_event.is_set():
                        break
                    self.ingest_page(page, history=not primed)
                    token = page.get('nextPageToken')
                    primed, attempts = True, 0
                    interval = max(self.settings['poll_seconds'], float(page.get('pollingIntervalMillis', 15000))/1000)
                    if page.get('offlineAt'):
                        self._state('ended', 'liveChatEnded')
                        break
                    self._state('connected')
                    self.stop_event.wait(interval)
                except YouTubeError as exc:
                    if exc.reason == 'invalidPageToken':
                        chat, token, primed = None, None, False
                        exc = YouTubeError('refreshingChatCursor', True)
                    if not exc.retryable:
                        self._state('error', exc.reason)
                        break
                    attempts += 1
                    self._state('retrying', exc.reason)
                    self.stop_event.wait(max(interval, min(60, 2**min(attempts, 6))))
                except Exception:
                    # The worker never prints or calls the world/voice/UI.
                    self._state('error', 'unexpectedResponse')
                    break
        finally:
            if self.stop_event.is_set():
                self._state('disconnected')

    def ingest_page(self, page, history=False):
        items = page.get('items', [])
        if not isinstance(items, list):
            raise YouTubeError('invalidResponse', True)
        with self.lock:
            for item in items:
                if not isinstance(item, dict):
                    continue
                identifier = item.get('id')
                if not isinstance(identifier, str) or not identifier or len(identifier) > 256 or identifier in self.seen:
                    continue
                self.seen.add(identifier); self.seen_order.append(identifier)
                if len(self.seen_order) > 2048:
                    self.seen.discard(self.seen_order.popleft())
                if history:
                    continue
                snippet, author = item.get('snippet', {}), item.get('authorDetails', {})
                if not isinstance(snippet, dict) or not isinstance(author, dict) or snippet.get('type') != 'textMessageEvent':
                    continue
                try:
                    date = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                    if date.tzinfo is None:
                        continue
                    published = date.timestamp()
                except (KeyError, ValueError, TypeError, AttributeError):
                    continue
                if published < max(self.fresh_after-1, self.wall_clock()-self.MESSAGE_TTL):
                    self.dropped += 1
                    self.skips['expired'] += 1
                    continue
                author_id = author.get('channelId')
                if not isinstance(author_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', author_id):
                    continue
                details = snippet.get('textMessageDetails', {})
                if not isinstance(details, dict):
                    continue
                text = clean_text(details.get('messageText', ''), 400)
                parsed = self.parse_message(text, self.settings['mode'])
                if parsed is None:
                    continue
                now = self.clock()
                # One fetch may contain comments posted many seconds apart.
                # Rate-limit their publication times, not their shared arrival.
                if published-self.authors.get(author_id, float('-inf')) < self.AUTHOR_COOLDOWN:
                    self.dropped += 1
                    self.skips['cooldown'] += 1
                    continue
                event = ChatMessage(identifier, author_id, clean_text(author.get('displayName', 'Viewer'), 50),
                                    *parsed, now)
                try:
                    self.messages_queue.put_nowait(event)
                except queue.Full:
                    # Keep recent comments, rather than letting a long spoken
                    # tick leave the queue full of expired messages forever.
                    try:
                        self.messages_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.messages_queue.put_nowait(event)
                    self.dropped += 1
                    self.skips['queue'] += 1
                self.authors[author_id] = published
                if len(self.authors) > 2048:
                    del self.authors[min(self.authors, key=self.authors.get)]
                self.received += 1

    @staticmethod
    def parse_message(text, mode):
        if text.startswith('!'):
            parts = text.split(None, 2)
            command = parts[0].lower()
            if command in ('!say', '!gift') and len(parts) == 3 and parts[2].strip():
                body = parts[2].strip().strip('"').strip()
                return (command[1:], parts[1], body) if body else None
            if command == '!gossip' and len(parts) >= 2:
                return 'gossip', '', text.split(None, 1)[1]
            return None
        if mode == 'all' and text and not text.startswith('/'):
            return 'say', '', text
        return None

    def status(self):
        with self.lock:
            identifier = self.settings['video_id'] or '(none)'
            return (f'YouTube {self.state} | stream {identifier} | mode {self.settings["mode"]} | '
                    f'queued {self.messages_queue.qsize()}/{self.QUEUE_LIMIT} | processed {self.processed} | '
                    f'dropped {self.dropped}'+(f' | {self.error}' if self.error else '')+
                    (' | Fix: '+ERROR_HELP[self.error] if self.error in ERROR_HELP else '')+
                    (' | skips '+', '.join(f'{name}={count}' for name, count in self.skips.items() if count) if any(self.skips.values()) else ''))

    def command(self, raw):
        parts = raw.strip().split(None, 1)
        action = parts[0].lower() if parts else 'status'
        value = parts[1].strip() if len(parts) > 1 else ''
        if action == 'status' and not value:
            return self.status()
        if action == 'connect' and value:
            return self.connect(value)
        if action == 'reconnect' and not value:
            return self.connect()
        if action == 'disconnect' and not value:
            return self.disconnect()
        if action == 'mode' and value.lower() in ('all', 'commands'):
            value = value.lower()
            with self.lock:
                self.settings['mode'] = value
                self._clear_queue()
                _atomic_json(self.config_path, self.settings)
            return 'YouTube mode '+value+'. Queued messages cleared.'
        raise ValueError('Use /youtube setup | connect URL | reconnect | status | disconnect | mode commands/all | pump')

    def drain(self, world, force=False):
        """Apply at most one chat message per drain on the calling thread."""
        with self.lock:
            notice, self.notice = self.notice, None
        if notice:
            world.narrate(notice)
        if not force and self.clock()-self.last_processed < self.WORLD_COOLDOWN:
            return 0
        living = [p for p in world.lonks if p.alive]
        if not living:
            return 0
        for _ in range(self.QUEUE_LIMIT):
            try:
                event = self.messages_queue.get_nowait()
            except queue.Empty:
                return 0
            if self.clock()-event.received > self.MESSAGE_TTL:
                with self.lock:
                    self.dropped += 1
                    self.skips['expired'] += 1
                continue
            target = next((p for p in living if p.name.casefold() == event.target.casefold()), None) if event.target else random.choice(living)
            if target is None:
                world.narrate(f'YouTube: Lonk {event.target} not found; message skipped.')
                with self.lock:
                    self.dropped += 1
                    self.skips['target'] += 1
                return 0
            previous = getattr(world, '_youtube_narration', None)
            try:
                world._youtube_narration = {'actor': target, 'viewer': True}
                world.narrate(f'YouTube {event.author} tells {target.name}: {event.body}')
                speaker = 'YouTube:'+event.author_id
                if event.command == 'say':
                    target.hear(speaker, event.body, is_player=True)
                    reply = target.respond_to_player(event.body, speaker=speaker)
                    world._youtube_narration = {'actor': target, 'viewer': False}
                    world.narrate(f'💬 {target.name}: {reply}')
                elif event.command == 'gift':
                    result = target.receive_gift(event.body)
                    world._youtube_narration = {'actor': target, 'viewer': False, 'marker': '🎁'}
                    world.narrate(f'🎁 {target.name} received {event.body} from {event.author}! {result}')
                elif event.command == 'gossip':
                    target.seed_rumor(speaker, event.body)
                    world.narrate(f'📣 {target.name} heard the rumor from {event.author}.')
            finally:
                world._youtube_narration = previous
            with self.lock:
                self.processed += 1
            self.last_processed = self.clock()
            return 1
        return 0
