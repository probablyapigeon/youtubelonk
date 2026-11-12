"""YouTube intake, reconnects, secrets, and main-thread game integration."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from lonk_dialogue import DialogueGenerator
from lonk_live import event_details
from lonk_youtube import YouTubeBridge, YouTubeAPI, YouTubeError, video_id, clean_text
import test_lonk_live as live_tests


STREAM = 'TestVid1234'
KEY = 'fake_local_key_for_tests_only'


class Clock:
    def __init__(self):
        self.monotonic, self.wall = 50., 1000.
    def __call__(self):
        return self.monotonic
    def advance(self, seconds):
        self.monotonic += seconds
        self.wall += seconds


def message(identifier='one', author='UCone', text='!say Flonk hello', published=1000, name='Viewer'):
    return {'id': identifier, 'authorDetails': {'channelId': author, 'displayName': name},
            'snippet': {'type': 'textMessageEvent',
                        'publishedAt': datetime.fromtimestamp(published, timezone.utc).isoformat(),
                        'textMessageDetails': {'messageText': text}}}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)
        self.clock = Clock()
        self.bridge = YouTubeBridge(self.directory, clock=self.clock, wall_clock=lambda: self.clock.wall)
        self.addCleanup(self.bridge.close)
        patcher = patch.dict('os.environ', {'YOUTUBE_API_KEY': ''})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_watch_live_short_and_studio_urls(self):
        for url in (STREAM, f'https://studio.youtube.com/video/{STREAM}/livestreaming',
                    f'https://www.youtube.com/watch?v={STREAM}&t=2', f'https://youtu.be/{STREAM}',
                    f'https://youtube.com/live/{STREAM}'):
            self.assertEqual(video_id(url), STREAM)
        for url in ('', 'file:///abc', f'https://youtube.com.evil/watch?v={STREAM}',
                    f'http://youtube.com/watch?v={STREAM}', 'not a video'):
            with self.assertRaises(ValueError):
                video_id(url)

    def test_only_allowlisted_viewer_commands(self):
        self.assertEqual(self.bridge.parse_message('!say Flonk hi 👋', 'commands'), ('say', 'Flonk', 'hi 👋'))
        self.assertEqual(self.bridge.parse_message('!gift Flonk moss', 'commands'), ('gift', 'Flonk', 'moss'))
        self.assertEqual(self.bridge.parse_message('!gossip moss is shiny', 'commands'), ('gossip', '', 'moss is shiny'))
        for text in ('!quit', '!save', '!load secret.json', '!quotes load C:/file', '!tune Flonk attack 99',
                     '!youtube setup secret', '/quit', '!say Flonk ""'):
            self.assertIsNone(self.bridge.parse_message(text, 'all'))
        self.assertIsNone(self.bridge.parse_message('normal comment', 'commands'))
        self.assertEqual(self.bridge.parse_message('normal comment', 'all'), ('say', '', 'normal comment'))

    def test_terminal_controls_removed_but_emoji_sequences_kept(self):
        self.assertEqual(clean_text('\x1b[2Jhi\x07\n 🧑🏽‍🚀', 100), 'hi 🧑🏽‍🚀')
        self.assertEqual(len(clean_text('x'*1000, 400)), 400)

    def test_initial_history_duplicates_old_and_malformed_messages_are_ignored(self):
        b = self.bridge
        b.ingest_page({'items': [message('old')]}, history=True)
        self.assertTrue(b.messages_queue.empty())
        b.ingest_page({'items': [message('old'), message('new'), message('too-old', published=900),
                                  {'id': 'broken', 'snippet': None}]})
        b.ingest_page({'items': [message('new')]})
        self.assertEqual(b.messages_queue.qsize(), 1)
        self.assertEqual(b.messages_queue.get_nowait().identifier, 'new')
        self.assertEqual(b.received, 1)

    def test_author_cooldowns_use_channel_id_not_display_name(self):
        b = self.bridge
        b.ingest_page({'items': [message('1', 'UCa', name='Same'), message('2', 'UCb', name='Same'),
                                  message('3', 'UCa', name='New Name')]})
        self.assertEqual(b.messages_queue.qsize(), 2)
        self.clock.advance(10)
        b.ingest_page({'items': [message('4', 'UCa', published=self.clock.wall)]})
        self.assertEqual(b.messages_queue.qsize(), 3)

    def test_one_poll_can_accept_commands_sent_ten_seconds_apart(self):
        self.clock.advance(20)
        self.bridge.ingest_page({'items': [message('say', 'UCone', '!say Flonk hello', 1000),
                                             message('gift', 'UCone', '!gift Flonk moss', 1012)]})
        self.assertEqual(self.bridge.messages_queue.qsize(), 2)

    def test_status_explains_cooldown_skips(self):
        self.bridge.ingest_page({'items': [message('first'), message('second')]})
        self.assertIn('cooldown=1', self.bridge.status())

    def test_queue_is_bounded_and_stale_work_expires(self):
        b = self.bridge
        b.ingest_page({'items': [message(str(i), 'UC'+str(i)) for i in range(40)]})
        self.assertEqual(b.messages_queue.qsize(), 32)
        self.assertEqual(b.dropped, 8)
        self.clock.advance(61)
        world = SimpleNamespace(lonks=[SimpleNamespace(name='Flonk', alive=True)], narrate=Mock())
        self.assertEqual(b.drain(world), 0)
        self.assertTrue(b.messages_queue.empty())
        self.assertEqual(b.dropped, 40)
        world.narrate.assert_not_called()

    def test_busy_spoken_tick_retains_recent_chat_instead_of_only_expired_backlog(self):
        b = self.bridge
        b.ingest_page({'items': [message(str(i), 'UC'+str(i)) for i in range(32)]})
        self.clock.advance(80)
        b.ingest_page({'items': [message('newest', 'UCnew', '!say Flonk recent message', self.clock.wall)]})
        p = SimpleNamespace(name='Flonk', alive=True, hear=Mock(), respond_to_player=Mock(return_value='Hello.'))
        world = SimpleNamespace(lonks=[p], narrate=Mock())
        self.assertEqual(b.drain(world), 1)
        p.respond_to_player.assert_called_once_with('recent message', speaker='YouTube:UCnew')

    def test_settings_and_credentials_persist_separately_and_are_not_in_status(self):
        b = self.bridge
        with self.assertRaisesRegex(ValueError, 'setup'):
            b.connect(f'https://studio.youtube.com/video/{STREAM}/livestreaming')
        b.setup(KEY)
        self.assertNotIn(KEY, b.status())
        self.assertNotIn(KEY, b.config_path.read_text())
        restored = YouTubeBridge(self.directory)
        self.addCleanup(restored.close)
        self.assertEqual(restored.settings['video_id'], STREAM)
        self.assertEqual(restored._key(), KEY)
        self.assertEqual(restored.state, 'disconnected')

    def test_reconnect_starts_one_reader_and_disconnect_wakes_wait(self):
        b = self.bridge
        ready = threading.Event()
        def factory(key):
            api = Mock()
            api.resolve_chat.return_value = 'chat'
            def messages(chat, token):
                ready.set()
                return {'items': [], 'nextPageToken': 'next', 'pollingIntervalMillis': 30000}
            api.messages.side_effect = messages
            return api
        b.api_factory = Mock(side_effect=factory)
        b.setup(KEY)
        b.connect(STREAM)
        self.assertTrue(ready.wait(2))
        old = b.thread
        b.disconnect()
        self.assertFalse(old.is_alive())
        ready.clear()
        b.command('reconnect')
        self.assertTrue(ready.wait(2))
        self.assertIsNot(b.thread, old)
        self.assertEqual(b.api_factory.call_count, 2)
        b.disconnect()
        self.assertTrue(b.messages_queue.empty())

    def test_background_retry_respects_refresh_interval_and_does_not_print(self):
        b = self.bridge
        class Stop:
            def __init__(self): self.stopped, self.waits = False, []
            def is_set(self): return self.stopped
            def set(self): self.stopped = True
            def wait(self, seconds):
                self.waits.append(seconds)
                if len(self.waits) == 3: self.stopped = True
        b.stop_event = Stop()
        api = Mock()
        api.resolve_chat.return_value = 'chat'
        api.messages.side_effect = [
            {'items': [message('history')], 'nextPageToken': 'first', 'pollingIntervalMillis': 25000},
            YouTubeError('networkInterrupted', True),
            {'items': [message('new')], 'nextPageToken': 'second', 'pollingIntervalMillis': 25000}]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            b._run(api, STREAM)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(b.messages_queue.qsize(), 1)
        self.assertEqual([call.args[1] for call in api.messages.call_args_list], [None, 'first', 'first'])
        self.assertTrue(all(wait >= 25 for wait in b.stop_event.waits))

    def test_expired_chat_cursor_resets_and_skips_replayed_history(self):
        b = self.bridge
        class Stop:
            def __init__(self): self.stopped, self.waits = False, 0
            def is_set(self): return self.stopped
            def set(self): self.stopped = True
            def wait(self, seconds):
                self.waits += 1
                if self.waits >= 4: self.stopped = True
        b.stop_event = Stop()
        api = Mock()
        api.resolve_chat.return_value = 'chat'
        api.messages.side_effect = [
            {'items': [message('old')], 'nextPageToken': 'expired'},
            YouTubeError('invalidPageToken'),
            {'items': [message('replayed')], 'nextPageToken': 'fresh'},
            {'items': [message('replayed'), message('brand-new')], 'nextPageToken': 'next'}]
        b._run(api, STREAM)
        self.assertEqual(api.resolve_chat.call_count, 2)
        self.assertEqual([call.args[1] for call in api.messages.call_args_list], [None, 'expired', None, 'fresh'])
        self.assertEqual(b.messages_queue.qsize(), 1)
        self.assertEqual(b.messages_queue.get_nowait().identifier, 'brand-new')

    def test_one_message_per_tick_on_calling_thread(self):
        b = self.bridge
        p = SimpleNamespace(name='Flonk', alive=True, hear=Mock(), respond_to_player=Mock(return_value='Hello.'), gossip=[])
        threads = []
        world = SimpleNamespace(lonks=[p], narrate=lambda line: threads.append(threading.get_ident()))
        b.ingest_page({'items': [message('one', 'UCa'), message('two', 'UCb')]})
        self.assertEqual(b.drain(world), 1)
        self.assertEqual(b.drain(world), 0)
        self.clock.advance(2)
        self.assertEqual(b.drain(world), 1)
        self.assertTrue(all(identity == threading.get_ident() for identity in threads))
        p.respond_to_player.assert_any_call('hello', speaker='YouTube:UCa')
        self.assertIsNone(world._youtube_narration)


class APITests(unittest.TestCase):
    def test_only_get_requests_to_youtube_with_expected_live_chat_parameters(self):
        opener = Mock(side_effect=[io.BytesIO(json.dumps({'items': [{'liveStreamingDetails': {'activeLiveChatId': 'chat'}}]}).encode()),
                                   io.BytesIO(b'{"items": [], "nextPageToken": "n"}')])
        api = YouTubeAPI(KEY, opener=opener)
        self.assertEqual(api.resolve_chat(STREAM), 'chat')
        api.messages('chat', 'cursor')
        for call in opener.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(urlparse(request.full_url).hostname, 'www.googleapis.com')
        parameters = parse_qs(urlparse(opener.call_args.args[0].full_url).query)
        self.assertEqual(parameters['pageToken'], ['cursor'])
        self.assertEqual(parameters['maxResults'], ['200'])

    def test_http_errors_cannot_echo_credentials(self):
        payload = json.dumps({'error': {'message': 'bad key '+KEY, 'errors': [{'reason': 'keyInvalid'}]}}).encode()
        error = HTTPError('https://example.invalid/?key='+KEY, 403, 'key '+KEY, {}, io.BytesIO(payload))
        api = YouTubeAPI(KEY, opener=Mock(side_effect=error))
        with self.assertRaises(YouTubeError) as caught:
            api.resolve_chat(STREAM)
        self.assertEqual(str(caught.exception), 'keyInvalid')
        self.assertNotIn(KEY, str(caught.exception))
        self.assertFalse(caught.exception.retryable)

    def test_specific_google_restriction_error_is_not_lost_as_forbidden(self):
        payload = {'error': {'message': 'blocked '+KEY, 'errors': [{'reason': 'forbidden'}],
                             'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo',
                                          'reason': 'API_KEY_SERVICE_BLOCKED',
                                          'metadata': {'service': 'youtube.googleapis.com', 'consumer': 'projects/123456'}}]}}
        error = HTTPError('https://example.invalid/?key='+KEY, 403, 'Forbidden', {},
                          io.BytesIO(json.dumps(payload).encode()))
        api = YouTubeAPI(KEY, opener=Mock(side_effect=error))
        with self.assertRaises(YouTubeError) as caught:
            api.resolve_chat(STREAM)
        self.assertEqual(caught.exception.reason, 'API_KEY_SERVICE_BLOCKED')
        self.assertNotIn(KEY, str(caught.exception))

    def test_unknown_google_details_cannot_leak_key_as_reason(self):
        payload = {'error': {'errors': [{'reason': 'forbidden'}],
                             'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': KEY}]}}
        error = HTTPError('https://example.invalid', 403, 'Forbidden', {}, io.BytesIO(json.dumps(payload).encode()))
        with self.assertRaises(YouTubeError) as caught:
            YouTubeAPI(KEY, opener=Mock(side_effect=error)).resolve_chat(STREAM)
        self.assertEqual(caught.exception.reason, 'forbidden')

    def test_network_errors_are_retryable_and_missing_chat_waits(self):
        api = YouTubeAPI(KEY, opener=Mock(side_effect=URLError('offline')))
        with self.assertRaises(YouTubeError) as caught:
            api.resolve_chat(STREAM)
        self.assertTrue(caught.exception.retryable)
        api = YouTubeAPI(KEY, opener=Mock(return_value=io.BytesIO(b'{"items":[{}]}')))
        with self.assertRaises(YouTubeError) as caught:
            api.resolve_chat(STREAM)
        self.assertEqual(caught.exception.reason, 'waitingForLiveChat')
        self.assertTrue(caught.exception.retryable)


class WorldIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        live_tests.SpatialIntegrationTests.setUpClass()
        cls.sim = live_tests.SpatialIntegrationTests.sim

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.clock = Clock()
        self.bridge = YouTubeBridge(self.folder.name, clock=self.clock, wall_clock=lambda: self.clock.wall)
        self.addCleanup(self.bridge.close)

    def world(self):
        world, c, screen = live_tests.SpatialIntegrationTests().world()
        world.youtube_bridge = self.bridge
        return world, c, screen

    def test_viewer_words_learned_and_response_bubbles_only_belong_to_lonk(self):
        w, _, screen = self.world()
        self.bridge.ingest_page({'items': [message(text='!say Flonk fuuuuck', name='Plarp')]})
        with patch('lonk_live.time.sleep'), w.live_command_output():
            self.bridge.drain(w)
        lonk = w.get_lonk('Flonk')
        self.assertIn('fuuuuck', lonk.wordplay_state['expressive'])
        self.assertIn('YouTube:UCone', lonk.dialogue_state)
        self.assertIn('╭', screen.getvalue())
        w._youtube_narration = {'actor': lonk, 'viewer': True}
        details = event_details(w, 'YouTube Plarp tells Flonk: hello Grub!', {})
        self.assertEqual(details['actors'], [lonk])
        self.assertIsNone(details['speech'])
        w._youtube_narration = None

    def test_gifts_gossip_and_admin_rejection_use_real_world_without_shell_commands(self):
        w, _, _ = self.world()
        w.narrate, w.save = Mock(), Mock()
        self.bridge.ingest_page({'items': [message('gift', 'UCgift', '!gift Flonk big bag of seed'),
                                              message('gossip', 'UCgossip', '!gossip moss is extremely shiny'),
                                              message('attack', 'UCbad', '!load C:/secret.json')]})
        self.assertEqual(self.bridge.messages_queue.qsize(), 2)
        self.bridge.drain(w, force=True)
        self.assertEqual(w.get_lonk('Flonk').items[-1]['name'], 'big bag of seed')
        self.bridge.drain(w, force=True)
        self.assertTrue(any(any('moss is extremely shiny' in str(entry) for entry in p.gossip) for p in w.lonks))
        w.save.assert_not_called()

    def test_gossip_is_learned_as_a_rumor_and_reaches_a_neighbor(self):
        w, c, _ = self.world()
        w.narrate = Mock()
        rumor = 'Wronk is holding a secret poop'
        self.bridge.ingest_page({'items': [message('gossip', text='!gossip '+rumor)]})
        with patch('lonk_youtube.random.choice', side_effect=lambda options: options[0]):
            self.bridge.drain(w, force=True)
        source = w.lonks[0]
        self.assertTrue(any(entry[1] == 'rumor' and entry[2] == rumor for entry in source.gossip))
        self.assertIn('poop', source.knowledge)
        peer, subject = w.lonks[1:]
        with patch.object(self.sim.random, 'random', return_value=0), patch.object(self.sim.random, 'choice', side_effect=lambda options: options[0]):
            source.gossip_about(subject, peer)
        self.assertTrue(any(entry[1] == 'rumor' and entry[2] == rumor for entry in peer.gossip))

    def test_comments_are_delivered_between_spoken_lines_in_a_long_tick(self):
        w, _, _ = self.world()
        w._live_view.enabled = False
        def long_tick():
            for index in range(5):
                if index == 1:
                    self.bridge.ingest_page({'items': [message('gift', 'UCgift', '!gift Flonk poop', self.clock.wall)]})
                if index == 2:
                    self.bridge.ingest_page({'items': [message('rumor', 'UCrumor', '!gossip moss is funny', self.clock.wall)]})
                w.narrate('Flonk continues a long conversation.')
                self.clock.advance(25)
        w._advance_world_tick = long_tick
        with contextlib.redirect_stdout(io.StringIO()):
            w.world_tick()
        self.assertEqual(self.bridge.processed, 2)
        self.assertTrue(any(item['name'] == 'poop' for item in w.get_lonk('Flonk').items))

    def test_actual_tick_keeps_serving_chat_between_actions_under_time_cooldown(self):
        w, _, _ = self.world()
        w.narrate = Mock()
        self.bridge.ingest_page({'items': [message(str(i), 'UC'+str(i)) for i in range(5)]})
        w.starting_population, w.arrival_chance, w.dream_chance = 0, 0, 0
        w.wp_ab_state = {}
        for p in w.lonks:
            p.choose_action = Mock(return_value='idle')
            p.act = lambda action: self.clock.advance(3)
        w.civilization.begin_tick = Mock()
        w.civilization.finish_tick = Mock()
        w.civilization.extra_turns = Mock(return_value=[])
        with patch.object(self.sim, 'EPISTEMOLOGY_ON', False):
            w._advance_world_tick()
        self.assertEqual(self.bridge.processed, 4)
        self.assertEqual(self.bridge.messages_queue.qsize(), 1)

    def test_viewer_dialogue_contexts_are_isolated_and_bounded(self):
        generator = DialogueGenerator(SimpleNamespace(name='Flonk'))
        generator.generate_response('I found a blue mushroom', target='Player')
        generator.generate_response('I found a purple egg', target='YouTube:UCone')
        generator.generate_response('I found a red rock', target='YouTube:UCtwo')
        self.assertEqual(generator.generate_response('what did I find?', target='YouTube:UCone'), 'You found a purple egg.')
        for i in range(100):
            generator._memory('YouTube:UC'+str(i))
        self.assertLessEqual(len(generator.lonk.dialogue_state), 50)
        self.assertIn('Player', generator.lonk.dialogue_state)

    def test_hidden_setup_and_real_save_never_store_credentials_in_world(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.dict('os.environ', {'YOUTUBE_API_KEY': ''}):
            w = self.sim.LonkWorld(num_lonks=2)
            w.youtube_bridge = self.bridge
            with patch.object(self.sim.sys.stdin, 'isatty', return_value=True), patch('getpass.getpass', return_value=KEY):
                result = w.youtube_command('setup')
            self.assertNotIn(KEY, result)
            world_file = str(Path(self.folder.name)/'world.json')
            w.save(world_file)
            data = Path(world_file).read_text()
            self.assertNotIn(KEY, data)
            self.assertNotIn('youtube_bridge', data)
            self.assertEqual(self.bridge._key(), KEY)

    def test_interactive_status_mode_pump_and_quit_preserve_controls(self):
        w, _, _ = self.world()
        w.auto_mode, w.tts_error = False, None
        w.command_parser = self.sim.CommandParser()
        w.save, w._stop_tts_thread = Mock(), Mock()
        self.bridge.ingest_page({'items': [message(text='!say Flonk hello')]})
        commands = iter(['/youtube status', '/youtube pump', '/youtube mode all', '/youtube disconnect', 'quit'])
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input', side_effect=lambda prompt: next(commands)), patch.object(self.sim.time, 'sleep'):
            w.interactive_loop()
        self.assertNotIn('Error:', output.getvalue())
        self.assertEqual(self.bridge.processed, 1)
        self.assertEqual(self.bridge.settings['mode'], 'all')
        self.assertTrue(self.bridge.stop_event.is_set())
        w.save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
