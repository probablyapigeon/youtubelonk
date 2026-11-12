"""Offline Unicode expression and terminal presentation helpers."""
import hashlib
import os
import random
import re
import unicodedata

EMOJI_BASE = r'[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\u00A9\u00AE\u203C\u2049\u2122\u2139\u3030\u303D\u3297\u3299]'
EMOJI_PART = EMOJI_BASE + r'[\uFE0E\uFE0F]?[\U0001F3FB-\U0001F3FF]?'
EMOJIS = re.compile(r'(?:[#*0-9]\uFE0F?\u20E3|[\U0001F1E6-\U0001F1FF]{2}|' +
                    EMOJI_PART + r'(?:\u200D' + EMOJI_PART + r')*[\U000E0020-\U000E007E]*\U000E007F?)')
BODIES = ('🐸', '🐱', '🐶', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐷', '🐵',
          '🐙', '🦑', '🦀', '🐢', '🦎', '🐲', '🦄', '🐥', '🦉', '🦇', '🐝', '🐛',
          '🦋', '🐌', '🪲', '🦕', '🦖', '👾', '🤖', '👽')
MOOD_EMOJIS = {
    'happy': ('😄', '✨', '🥳', '💛'), 'excited': ('🤩', '🎉', '⚡', '✨'),
    'sad': ('😢', '🥺', '🌧️'), 'angry': ('😠', '💢', '🔥'),
    'afraid': ('😨', '🫣', '😰'), 'calm': ('🌿', '😌', '🕊️'),
    'curious': ('🤔', '🔎', '👀'), 'love': ('💕', '🥰', '💖'),
}
# Use the local Python Unicode database, including assigned pictographs outside
# the mood examples. No download or language model is needed to explore them.
EMOJI_ALPHABET = tuple(chr(n) for start, end in ((0x1F300, 0x1FB00), (0x2600, 0x2800), (0x2B00, 0x2C00))
                       for n in range(start, end) if unicodedata.category(chr(n)) == 'So')


def body_for(lonk):
    identity = str(getattr(lonk, 'semantic_id', None) or lonk.name)
    return BODIES[int.from_bytes(hashlib.sha256(identity.encode('utf-8')).digest()[:4], 'big') % len(BODIES)]


def learn_emojis(text, state):
    learned = state.setdefault('emojis', {})
    for emoji in EMOJIS.findall(text):
        if emoji not in learned:
            state['pending_emoji'] = emoji
        learned[emoji] = min(20, learned.get(emoji, 0) + 1)
    if len(learned) > 256:
        keep = sorted(learned, key=lambda e: learned[e], reverse=True)[:256]
        state['emojis'] = {e: learned[e] for e in keep}


def express_emojis(reply, state, include_mood=False):
    learned = state.get('emojis', {})
    pending = state.pop('pending_emoji', None)
    if pending:
        return reply + ' ' + pending if pending not in reply else reply
    if not learned and not include_mood:
        return reply
    if random.random() >= 0.18:
        return reply
    options = list(learned)
    if not options and include_mood:
        options = [emoji for mood, emojis in MOOD_EMOJIS.items()
                   if mood in reply.lower() for emoji in emojis]
    if include_mood and (not options or random.random() < 0.1):
        options = list(EMOJI_ALPHABET)
    options = [e for e in options if e not in reply and e != state.get('last_emoji')] or options
    if options:
        emoji = random.choice(options)
        state['last_emoji'] = emoji
        return reply + ' ' + emoji
    return reply


def display_width(text):
    # Treat a joined emoji/flag/keycap as one two-column glyph.
    plain = EMOJIS.sub('界', text)
    return sum(0 if unicodedata.combining(c) or c in '\uFE0E\uFE0F\u200D' else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in plain)


def wrap_display(text, width):
    lines, line = [], ''
    for word in text.split():
        if line and display_width(line + ' ' + word) > width:
            lines.append(line)
            line = ''
        if display_width(word) > width:
            for glyph in re.findall(EMOJIS.pattern + r'|.', word):
                if display_width(line + glyph) > width:
                    lines.append(line)
                    line = ''
                line += glyph
        else:
            line += (' ' if line else '') + word
    return lines + ([line] if line else []) or ['']


RESET = '\x1b[0m'


def event_color(text):
    low = text.lower()
    if '⚔' in text or '💀' in text:
        return '\x1b[91m'
    if '💕' in text:
        return '\x1b[95m'
    if '🏙' in text:
        return '\x1b[92m'
    if '🚶' in text:
        return '\x1b[96m'
    if any(symbol in text for symbol in ('╭', '╰', '│', '▶')):
        return '\x1b[96m'
    if re.search(r'\b(attacks?|bonks?|pounces?|lunges?|scammed|extorts?|dissolves|jealous)\b', low):
        return '\x1b[91m'
    if re.search(r'\b(crush|love|heartbreak|born|romance)\b', low):
        return '\x1b[95m'
    if re.search(r'\b(city|outpost|settlement|grows into|recover|heals?|helps?)\b', low):
        return '\x1b[92m'
    if re.search(r'\b(trades?|coins?|acquired|discovers?|gives?|gift|market|shiny)\b', low):
        return '\x1b[93m'
    if re.search(r'\b(dream|cult|shrine|holy|axiom|annex)\b', low):
        return '\x1b[94m'
    if '→' in text or re.search(r'\b(teaches|whispers|school|lonks:|world map)\b', low):
        return '\x1b[96m'
    if text.lstrip().startswith(('+---', '| Paths:', '| To ')):
        return '\x1b[90m'
    return '\x1b[37m'


class ColorOutput:
    """Color ordinary console writes; pass through paced single characters."""
    def __init__(self, output):
        self.output = output

    def write(self, text):
        if '\x1b[' in text or not text.strip() or len(text) == 1:
            self.output.write(text)
        else:
            for line in text.splitlines(keepends=True):
                self.output.write(event_color(line) + line + RESET)
        return len(text)

    def flush(self):
        self.output.flush()

    def __getattr__(self, name):
        return getattr(self.output, name)


def terminal_controls_available(output):
    if not getattr(output, 'isatty', lambda: False)():
        return False
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetConsoleMode.restype = wintypes.BOOL
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.SetConsoleMode.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-11)
        mode = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(mode)) or not kernel.SetConsoleMode(handle, mode.value | 4):
            return False
    elif os.environ.get('TERM') == 'dumb':
        return False
    return True


def enable_colors(output):
    if os.environ.get('NO_COLOR') is not None or not terminal_controls_available(output):
        return output
    return ColorOutput(output)
