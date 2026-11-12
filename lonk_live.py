"""A main-thread terminal dashboard sharing the simulation's narration stream."""
import copy
import re
import shutil
import time
from collections import deque

from lonk_map import render_map, _clip, item_label
from lonk_visuals import ColorOutput, RESET, body_for, event_color, wrap_display, terminal_controls_available


def event_details(world, text, previous_positions):
    """Attach live actors and real room IDs to an existing narration event."""
    civilization = world.civilization
    ids = {name: str(i) for i, name in enumerate(civilization.rooms, 1)}
    # Names inside an utterance or rumor are topics, not participants.
    head = text.split(':', 1)[0]
    has_named_head = any(re.search(r'(?<!\w)'+re.escape(p.name)+r'(?!\w)', head) for p in world.lonks)
    action_text = head if ':' in text and has_named_head else text
    action_text = re.split(r'\b(?:the word|about you|about)\b', action_text, maxsplit=1)[0]
    matches = []
    for lonk in world.lonks:
        match = re.search(r'(?<!\w)' + re.escape(lonk.name) + r'(?!\w)', action_text)
        if match:
            matches.append((match.start(), lonk))
    actors = [p for _, p in sorted(matches, key=lambda entry: entry[0])]
    low = action_text.lower()
    if '→' in action_text or re.search(r'\b(whispers|gossips|teaches|says|asks)\b', low):
        marker = '💬'
    elif re.search(r'\b(attacks?|bonks?|pounces?|lunges?|swings|jealousy)\b', low):
        marker = '⚔️'
    elif re.search(r'\b(dissolves|dies|death)\b', low):
        marker = '💀'
    elif re.search(r'\b(crush|love|romance|heartbreak|born)\b', low):
        marker = '💕'
    elif re.search(r'\b(gives?|trades?|exchanges|purchase|gift|scammed)\b', low):
        marker = '🎁'
    elif re.search(r'\b(moves|wanders)\b', low):
        marker = '🚶'
    elif re.search(r'\b(dream|trance)\b', low):
        marker = '💤'
    elif re.search(r'\b(settlement|grows into|annex)\b', low):
        marker = '🏙️'
    elif re.search(r'\b(discovers|acquired)\b', low):
        marker = '💎'
    else:
        marker = '💬'
    youtube = getattr(world, '_youtube_narration', None)
    if youtube:
        actors = [youtube['actor']]
        marker = youtube.get('marker', '💬')
    rooms = list(dict.fromkeys(p.territory for p in actors if p.territory in ids))
    if not rooms:
        rooms = [name for name in ids if name in text]
    travel = None
    for p in actors:
        old = previous_positions.get(p.name)
        if marker == '🚶' and old and old != p.territory and p.territory in civilization.edges.get(old, []):
            travel = (p, old, p.territory)
            break
    if travel:
        rooms = list(dict.fromkeys([travel[1], travel[2]]+rooms))
    labels = [f'[{ids[name]}] {name}' for name in rooms]
    prefix = marker + ' ' + (' / '.join(labels) if labels else 'World') + ' | '
    speech = None
    if actors and marker == '💬' and not (youtube and youtube.get('viewer')) and (text.lstrip().startswith('💬') or '→' in head or
                                      re.search(r'\b(says?|asks?|whispers|gossips)\b', head, re.I)):
        separator = re.search(r':\s*', text)
        if separator:
            speech = {'speaker': actors[0], 'start': separator.end()}
    return {'actors': actors, 'rooms': rooms, 'marker': marker, 'prefix': prefix,
            'travel': travel, 'speech': speech}


class _EventOutput:
    def __init__(self, view):
        self.view = view

    def write(self, text):
        self.view.current += text.rstrip('\n')
        self.view.draw(force='\n' in text)
        return len(text)

    def flush(self):
        pass


class TerminalWorldView:
    def __init__(self, world, output, size=None):
        self.world = world
        self.color = isinstance(output, ColorOutput)
        self.output = output.output if self.color else output
        self.size = size
        self.enabled = terminal_controls_available(output)
        self.feed = deque(maxlen=100)
        self.positions = {p.name: p.territory for p in world.lonks}
        self.current = ''
        self.event = None
        self.last_event = None
        self.last_draw = 0
        self.event_output = _EventOutput(self)
        self.map_cache = {}
        self.travel_fraction = None

    def reset(self):
        self.feed.clear()
        self.positions = {p.name: p.territory for p in self.world.lonks}
        self.current, self.event, self.last_event = '', None, None
        self.travel_fraction = None
        self.map_cache.clear()

    def dimensions(self):
        size = self.size or shutil.get_terminal_size(fallback=(100, 36))
        return max(40, size[0]-1), max(18, size[1])

    def fits_terminal(self):
        width, height = self.size or shutil.get_terminal_size(fallback=(100, 36))
        return width >= 41 and height >= 18

    def begin_tick(self):
        self.output.write('\x1b[2J\x1b[H\x1b[?25l')
        self.draw(force=True)

    def begin_event(self, text):
        self.current = ''
        self.event = event_details(self.world, text, self.positions)
        self.event['length'] = max(1, len(text))
        self.map_cache.clear()
        self.draw(force=True)

    def _map(self, width, height):
        civilization = self.world.civilization
        names = list(civilization.rooms)
        columns = 3 if width >= 76 else 2 if width >= 54 else 1
        capacity = columns * max(1, (height-10)//7)
        active = self.event or self.last_event or {}
        focus = active.get('rooms', [])
        focus_name = focus[0] if focus else names[0] if names else None
        active_travel = active.get('travel')
        if active_travel and (self.event is None or len(self.current)/active['length'] >= 0.5):
            focus_name = active_travel[2]
        index = names.index(focus_name) if focus_name in names else 0
        start = index//capacity*capacity
        visible = names[start:start+capacity]
        view = copy.copy(civilization)
        view.rooms = {name: civilization.rooms[name] for name in visible}
        view.map_ids = {name: str(i) for i, name in enumerate(names, 1)}
        view.world = copy.copy(self.world)
        view.world.lonks = [p for p in self.world.lonks if p.territory in view.rooms]
        view.world.lonks.sort(key=lambda p: p not in active.get('actors', []))
        markers = {room: active['marker'] for room in focus if room in view.rooms}
        travel = (self.event or {}).get('travel')
        fraction = self.travel_fraction if self.travel_fraction is not None else min(1, len(self.current)/self.event['length']) if self.event else 1
        actors = active.get('actors', [])
        interaction = (actors[0], actors[1], active['marker'], fraction) if (
            len(actors) >= 2 and actors[0].territory == actors[1].territory
            and active['marker'] in ('🎁', '⚔️', '💕')) else None
        view.map_interaction = interaction
        speech = (self.event or {}).get('speech')
        bubble_text = self.current[speech['start']:] if speech else ''
        view.map_bubble = (speech['speaker'], bubble_text) if speech else None
        travelling = None
        if travel and all(room in view.rooms for room in travel[1:]):
            # While in transit, the map body is on the actual connecting path.
            if fraction < 1:
                view.world.lonks = [p for p in view.world.lonks if p is not travel[0]]
                travelling = (*travel, fraction)
        cache_key = (width, height, tuple(visible), int(100*fraction) if travelling or interaction else -1,
                     bubble_text if speech else None)
        if cache_key not in self.map_cache:
            if len(self.map_cache) >= 32:
                self.map_cache.clear()
            graph = render_map(view, width, compact=True, markers=markers, travelling=travelling).splitlines()[3:]
            while graph and not graph[0].strip():
                graph.pop(0)
            while graph and not graph[-1].strip():
                graph.pop()
            self.map_cache[cache_key] = graph
        page = f'Rooms {start+1}-{start+len(visible)} of {len(names)}' if len(visible) < len(names) else 'All rooms'
        return self.map_cache[cache_key], page

    def draw(self, force=False):
        now = time.monotonic()
        if not force and now-self.last_draw < 1/30:
            return
        self.last_draw = now
        width, height = self.dimensions()
        graph, page = self._map(width, height)
        status = f'LONK WORLD | Tick {self.world.tick} | {page} | /map full view'
        info = 'Markers show the current event. Ctrl+C pauses auto; /live off uses scrolling output.'
        active = self.event or self.last_event
        if active and active['actors']:
            actor = active['actors'][0]
            items = ', '.join(item_label(i) for i in getattr(actor, 'items', [])) or '(nothing)'
            info = body_for(actor)+' '+actor.name+' | '+str(actor.territory)+' | Carrying: '+items
        header = [_clip(status, width), _clip(info, width)]
        feed_lines = []
        for line in self.feed:
            feed_lines.extend(wrap_display(line, width))
        if self.event:
            feed_lines.extend(wrap_display(self.event['prefix']+self._decorate(self.current, self.event), width))
        available = max(2, height-len(graph)-len(header)-3)
        frame = header+graph+['─'*width]+feed_lines[-available:]
        # Leave the bottom row available for the existing input prompt.
        frame = frame[:height-1]
        painted = [(event_color(line)+line+RESET) if self.color else line for line in frame]
        self.output.write('\x1b[H'+'\x1b[K\n'.join(painted)+'\x1b[K\x1b[J\n')
        self.output.flush()

    def end_event(self):
        if self.event:
            self.feed.append(self.event['prefix']+self._decorate(self.current, self.event))
            self.last_event = self.event
        self.current, self.event = '', None
        self.positions = {p.name: p.territory for p in self.world.lonks}
        self.map_cache.clear()
        self.draw(force=True)

    @staticmethod
    def _decorate(text, event):
        actors = {p.name: p for p in event['actors']}
        if not actors:
            return text
        pattern = r'(?<!\w)(?:'+'|'.join(re.escape(name) for name in sorted(actors, key=len, reverse=True))+r')(?!\w)'
        return re.sub(pattern, lambda m: body_for(actors[m[0]])+' '+m[0], text)

    def finish_tick(self):
        self.map_cache.clear()
        try:
            self.draw(force=True)
        finally:
            self.output.write('\x1b[?25h')
            self.output.flush()

    def narrate(self, text, callback):
        from contextlib import redirect_stdout
        self.begin_event(text)
        try:
            if not getattr(self.world, 'tts_enabled', False) and (self.event['travel'] or (
                    len(self.event['actors']) >= 2 and self.event['marker'] in ('🎁', '⚔️', '💕'))):
                for fraction in (0.2, 0.5, 0.8):
                    self.travel_fraction = fraction
                    self.draw(force=True)
                    time.sleep(0.04)
                self.travel_fraction = None
            with redirect_stdout(self.event_output):
                callback()
            if not getattr(self.world, 'tts_enabled', False):
                speech = self.event.get('speech')
                delay = min(2.5, max(0.6, len(self.current[speech['start']:])/45)) if speech else 0.08
                time.sleep(delay)
        finally:
            self.travel_fraction = None
            self.end_event()
