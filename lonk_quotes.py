"""Local text corpora feed the existing, bounded phrase learner. No network."""
import json
from pathlib import Path
import random
import shlex

from lonk_visuals import learn_emojis


class QuoteLibrary:
    MAX_QUOTES = 5000
    MAX_LENGTH = 2000
    MAX_FILE_BYTES = 2_000_000

    def __init__(self):
        self.quotes = []
        self.enabled = False
        self.interval = 12
        self.last_tick = None
        self.last_quote = {}

    @classmethod
    def _validated(cls, rows):
        if not isinstance(rows, list):
            raise ValueError('Quote data must be a list of strings or objects with quote/text fields.')
        quotes, seen = [], set()
        for index, row in enumerate(rows, 1):
            text = row.get('quote', row.get('text')) if isinstance(row, dict) else row
            if not isinstance(text, str):
                raise ValueError(f'Quote {index} needs a text or quote string.')
            text = ' '.join(text.split())
            if not text:
                continue
            if len(text) > cls.MAX_LENGTH:
                raise ValueError(f'Quote {index} exceeds {cls.MAX_LENGTH} characters; split it into shorter entries.')
            if text.casefold() not in seen:
                seen.add(text.casefold())
                quotes.append(text)
            if len(quotes) > cls.MAX_QUOTES:
                raise ValueError(f'Use at most {cls.MAX_QUOTES} distinct quotes per library.')
        return quotes

    def load_file(self, filename):
        path = Path(filename).expanduser()
        if path.stat().st_size > self.MAX_FILE_BYTES:
            raise ValueError('Quote files must be at most 2 MB.')
        text = path.read_text(encoding='utf-8-sig')
        if path.suffix.lower() == '.json':
            rows = json.loads(text)
            if isinstance(rows, dict):
                rows = rows.get('quotes')
        elif path.suffix.lower() in ('.jsonl', '.ndjson'):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            rows = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        quotes = self._validated(rows)
        if not quotes:
            raise ValueError('No quotes found. Put one quote per line in a UTF-8 text file.')
        # Import atomically: a bad file cannot erase a working library.
        self.quotes, self.last_quote = quotes, {}
        return len(quotes)

    def teach(self, world, lonk):
        if not self.quotes:
            raise ValueError('Load a quote file first: /quotes load FILE')
        if not lonk.alive:
            raise ValueError('Choose a living Lonk.')
        options = [q for q in self.quotes if q != self.last_quote.get(lonk.name)] or self.quotes
        quote = random.choice(options)
        lonk.hear('Quote Archive', quote)
        generator = lonk.dialogue_generator
        state = generator._learn_words(quote, source='Player')
        learn_emojis(quote, state)
        # The archive is an outside lesson, not an assertion about the world.
        # Learn short chunks using the same machinery as player-taught sayings.
        if not generator._learn_phrase(quote, state) and len(quote) <= 100:
            generator._remember_phrase(quote, state)
        self.last_quote[lonk.name] = quote
        if len(self.last_quote) > 256:
            del self.last_quote[next(iter(self.last_quote))]
        lonk.last_spoken = quote
        world.narrate(f'💬 {lonk.name}: {quote}')
        # Nearby listeners hear the reading; no remote classroom or global copy.
        for peer in lonk.nearby_lonks():
            peer.hear(lonk, quote)
        return quote

    def maybe_teach(self, world):
        if not self.enabled or not self.quotes:
            return
        if self.last_tick is not None and world.tick-self.last_tick < self.interval:
            return
        living = [p for p in world.lonks if p.alive]
        if living:
            self.teach(world, random.choice(living))
            self.last_tick = world.tick

    def command(self, world, raw):
        # Keep backslashes in Windows paths; quoted paths may contain spaces.
        args = [s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in '\"\'' else s
                for s in shlex.split(raw, posix=False)]
        action = args[0].lower() if args else 'status'
        if action in ('load', 'import') and len(args) == 2:
            count = self.load_file(args[1])
            return f'Loaded {count} quotes. Use /quotes teach NAME, or /quotes on.'
        if action == 'teach' and len(args) == 2:
            lonk = next((p for p in world.lonks if p.name.casefold() == args[1].casefold() and p.alive), None)
            if lonk is None:
                raise ValueError(f"Living Lonk '{args[1]}' not found.")
            self.teach(world, lonk)
            return None
        if action == 'on' and len(args) <= 2:
            if not self.quotes:
                raise ValueError('Load a quote file first: /quotes load FILE')
            interval = int(args[1]) if len(args) == 2 else self.interval
            if not 1 <= interval <= 10000:
                raise ValueError('Quote interval must be 1 to 10000 ticks.')
            self.interval, self.enabled, self.last_tick = interval, True, world.tick
            return f'Quote learning ON: one Lonk reads one quote every {interval} ticks.'
        if action == 'off' and len(args) == 1:
            self.enabled = False
            return 'Quote learning OFF. Lonks keep words and phrases they already learned.'
        if action == 'clear' and len(args) == 1:
            self.quotes, self.enabled, self.last_quote = [], False, {}
            return 'Quote library cleared. Previously learned phrases remain in Lonk memory.'
        if action == 'status' and len(args) <= 1:
            return f'Quote library: {len(self.quotes)} quotes; auto learning {"ON" if self.enabled else "OFF"}; interval {self.interval} ticks.'
        raise ValueError('Usage: /quotes load FILE | teach NAME | on [TICKS] | off | status | clear')

    def to_dict(self):
        return {'quotes': self.quotes, 'enabled': self.enabled, 'interval': self.interval,
                'last_tick': self.last_tick, 'last_quote': self.last_quote}

    @classmethod
    def from_dict(cls, data):
        result = cls()
        if not data:
            return result
        result.quotes = cls._validated(data.get('quotes', []))
        interval = data.get('interval', 12)
        if not isinstance(interval, int) or not 1 <= interval <= 10000:
            raise ValueError('Saved quote interval must be 1 to 10000 ticks.')
        result.interval = interval
        result.enabled = bool(data.get('enabled')) and bool(result.quotes)
        last_tick = data.get('last_tick')
        result.last_tick = last_tick if isinstance(last_tick, int) else None
        result.last_quote = {str(k): v for k, v in list(data.get('last_quote', {}).items())[-256:] if v in result.quotes}
        return result
