"""Read-only, connected terminal view of the live civilization graph."""
import heapq
import re
import shutil
from lonk_visuals import EMOJIS, body_for, display_width, wrap_display


def item_label(item):
    name = str(item.get('name', 'Unknown item')) if isinstance(item, dict) else str(item)
    icons = (('portal', '🌀'), ('shield', '🛡️'), ('acorn', '🌰'), ('moss', '🌿'),
             ('seed', '🌱'), ('sock', '🧦'), ('rock', '🪨'), ('egg', '🥚'),
             ('shard', '💎'), ('pickle', '🥒'))
    return next((icon for word, icon in icons if word in name.lower()), '📦') + ' ' + name


def _room_lines(civilization, name, ids, occupants):
    room = civilization.rooms[name]
    level = room.get('level', 0)
    kind = 'ANNEX' if room.get('parent') else 'CITY' if level >= 2 else 'OUTPOST' if level == 1 else 'WILDS'
    title = room.get('display_name', name)
    body = [f'[{ids[name]}] {kind}: {title}']
    if title != name:
        body.append('Formerly: ' + name)
    if room.get('parent'):
        body.append('Annex of: [' + ids.get(room['parent'], '?') + '] ' + room['parent'])
    people = occupants.get(name, [])
    body.append('Lonks:' if people else 'Lonks: (empty)')
    for lonk in people:
        body.append(body_for(lonk) + ' ' + lonk.name)
        body.append('Carrying: ' + (', '.join(item_label(item) for item in getattr(lonk, 'items', [])) or '(nothing)'))
    neighbors = [ids[n] for n in civilization.edges.get(name, []) if n in ids]
    body.append('Paths: ' + (', '.join('[' + n + ']' for n in neighbors) or '(none)'))
    dropped = room.get('dropped', [])
    body.append('Ground: ' + (', '.join(item_label(item) for item in dropped) or '(empty)'))
    if not room.get('parent') and level < 2:
        target = 'city' if level == 1 else 'outpost'
        threshold = civilization.settings['city_ticks' if level == 1 else 'settlement_ticks']
        ticks = room.get('density_ticks', 0)
        filled = min(10, int(10 * ticks / threshold))
        body.append(f'To {target}: [{"#" * filled}{"." * (10-filled)}] {ticks}/{threshold} crowded ticks')
        body.append(f'Dropped items: {len(dropped)}/{11 if level == 1 else 6} for growth')
    if name in civilization.schools:
        body.append('School')
    if room.get('shrines'):
        body.append('Shrines: ' + ', '.join(room['shrines']))
    if room.get('laws'):
        body.append('Laws: ' + ', '.join(room['laws']))
    return body


def _route(start, end, blocked, used, width, height):
    """Route a real edge through open space, avoiding existing trails if possible."""
    frontier, costs, previous = [(0, start)], {start: 0}, {}
    while frontier:
        cost, cell = heapq.heappop(frontier)
        if cost != costs[cell]:
            continue
        if cell == end:
            path = [end]
            while path[-1] != start:
                path.append(previous[path[-1]])
            return list(reversed(path))
        x, y = cell
        for nxt in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            nx, ny = nxt
            if not (0 <= nx < width and 0 <= ny < height) or nxt in blocked:
                continue
            score = cost + 1 + (12 if nxt in used else 0)
            if score < costs.get(nxt, float('inf')):
                costs[nxt], previous[nxt] = score, cell
                heapq.heappush(frontier, (score, nxt))
    raise ValueError('Unable to route map path')


def _layout(civilization, width, compact=False, markers=None):
    names = list(civilization.rooms)
    ids = getattr(civilization, 'map_ids', {name: str(i) for i, name in enumerate(names, 1)})
    occupants = {}
    for lonk in civilization.world.lonks:
        if lonk.alive:
            occupants.setdefault(lonk.territory, []).append(lonk)
    width = max(40, min(140, width))
    columns = (3 if width >= 76 else 2 if width >= 54 else 1) if compact else (2 if width >= 76 else 1)
    margin, gap = (2, 4) if compact else (3, 8)
    card_width = (width - 2*margin - gap*(columns-1)) // columns
    bodies = {name: [part for line in _room_lines(civilization, name, ids, occupants)
                     for part in wrap_display(line, card_width-4)] for name in names}
    if compact:
        for name in names:
            room = civilization.rooms[name]
            kind = 'ANNEX' if room.get('parent') else 'CITY' if room.get('level', 0) >= 2 else 'OUTPOST' if room.get('level') else ''
            label = f'[{ids[name]}] ' + (markers or {}).get(name, '') + room.get('display_name', name)
            people = ' '.join(body_for(p)+' '+p.name for p in occupants.get(name, [])) or '(empty)'
            items = sum(len(getattr(p, 'items', [])) for p in occupants.get(name, []))
            detail = f'{kind} Items:{items} Ground:{len(room.get("dropped", []))}'.strip()
            bodies[name] = [_clip(text, card_width-4) for text in (label, people, detail)]
            interaction = getattr(civilization, 'map_interaction', None)
            if interaction and interaction[0].territory == name:
                first, second, _, _ = interaction
                bodies[name][2] = body_for(first)+' '+'_'*(card_width-10)+' '+body_for(second)
            bubble = getattr(civilization, 'map_bubble', None)
            if bubble and bubble[0].territory == name:
                speaker, spoken = bubble
                inner = card_width-6
                heading = _clip('💬 '+body_for(speaker)+' '+speaker.name, inner)
                lines = wrap_display(spoken, inner)[-3:]
                # Reserve the same space from the start of the utterance so
                # typing does not make the room and trails jump every word.
                lines += ['']*(3-len(lines))
                bodies[name][1] = _clip('▶ '+people, card_width-4)
                bodies[name] += ['╭'+heading+'─'*(inner-display_width(heading))+'╮']
                bodies[name] += ['│'+line+' '*(inner-display_width(line))+'│' for line in lines]
                bodies[name] += ['╰'+'─'*inner+'╯']
    cards, y = {}, 3
    for row in range((len(names)+columns-1)//columns):
        group = names[row*columns:(row+1)*columns]
        height = max(len(bodies[name])+2 for name in group)
        for col, name in enumerate(group):
            if row % 2:
                col = columns-1-col
            cards[name] = (margin+col*(card_width+gap), y, card_width, height)
        y += height+(2 if compact else 5)
    height = max(6, y-2)
    blocked = {(x, y) for bx, by, bw, bh in cards.values()
               for x in range(bx, bx+bw) for y in range(by, by+bh)}
    edges = sorted({tuple(sorted((name, other))) for name, neighbors in civilization.edges.items()
                    if name in cards for other in neighbors if other in cards and other != name})
    edges.sort(key=lambda pair: (abs(cards[pair[0]][0]-cards[pair[1]][0]) +
                                 abs(cards[pair[0]][1]-cards[pair[1]][1]), pair))
    ports, used, routes = {}, set(), []

    def port(name, other):
        x, y, w, h = cards[name]
        ox, oy, _, _ = cards[other]
        if ox != x and oy != y:
            # Long diagonal links use the outer perimeter, keeping local
            # room-to-room trails readable in the central corridor.
            side = 'left' if x == margin else 'right'
        else:
            side = ('right' if ox > x else 'left') if ox != x else ('bottom' if oy > y else 'top')
        index = ports.get((name, side), 0)
        ports[name, side] = index+1
        if side in ('top', 'bottom'):
            px = x+w//2+index % max(1, w//2-2)
            return (px, y if side == 'top' else y+h-1), (px, y-1 if side == 'top' else y+h)
        py = y+1+index % (h-2)
        return (x if side == 'left' else x+w-1, py), (x-1 if side == 'left' else x+w, py)

    for first, second in edges:
        a, start = port(first, second)
        b, end = port(second, first)
        path = [a]+_route(start, end, blocked, used, width, height)+[b]
        used.update(path)
        routes.append((first, second, path))
    return width, height, cards, bodies, routes, occupants


def _clip(text, width):
    if display_width(text) <= width:
        return text
    return wrap_display(text, width-1)[0] + '…'


def render_map(civilization, width=None, compact=False, markers=None, travelling=None):
    if width is None:
        width = shutil.get_terminal_size(fallback=(80, 24)).columns-1
    width, height, cards, bodies, routes, occupants = _layout(civilization, width, compact, markers)
    canvas = [[' ']*width for _ in range(height)]

    def put(x, y, text):
        for glyph in re.findall(EMOJIS.pattern+r'|.', text):
            span = display_width(glyph)
            if span == 0:
                continue
            canvas[y][x] = glyph
            for extra in range(1, span):
                canvas[y][x+extra] = ''
            x += span

    for name, (x, y, w, h) in cards.items():
        put(x, y, '+'+'-'*(w-2)+'+')
        for row in range(1, h-1):
            text = bodies[name][row-1] if row <= len(bodies[name]) else ''
            put(x, y+row, '| '+text+' '*(w-4-display_width(text))+' |')
        put(x, y+h-1, '+'+'-'*(w-2)+'+')
    visits = set()
    for _, _, path in routes:
        for index, (x, y) in enumerate(path):
            if index in (0, len(path)-1):
                canvas[y][x] = '+'
                continue
            before, after = path[index-1], path[index+1]
            if before[1] == after[1]:
                glyph = '_'
            elif before[0] == after[0]:
                glyph = '|'
            else:
                directions = {(before[0]-x, before[1]-y), (after[0]-x, after[1]-y)}
                glyph = '\\' if directions in ({(1, 0), (0, 1)}, {(-1, 0), (0, -1)}) else '/'
            canvas[y][x] = 'x' if (x, y) in visits else glyph
            visits.add((x, y))
    if travelling:
        lonk, source, destination, fraction = travelling
        route = next((path if first == source else list(reversed(path))
                      for first, second, path in routes if {first, second} == {source, destination}), None)
        if route:
            x, y = route[min(len(route)-1, int(fraction*(len(route)-1)))]
            if x < width-1:
                put(x, y, body_for(lonk))
    interaction = getattr(civilization, 'map_interaction', None)
    if compact and interaction and interaction[0].territory in cards:
        first, _, marker, fraction = interaction
        x, y, w, _ = cards[first.territory]
        offset = 3+int(max(0, min(1, fraction))*max(0, w-12))
        put(x+2+offset, y+3, marker)
    world = civilization.world
    lines = [f'WORLD MAP | Tick {world.tick} | {sum(map(len, occupants.values()))} living Lonks',
             'Trails connect rooms. x = crossing, not a junction. Paths list destinations.',
             'Emoji = Lonk body; Carrying = inventory; Ground = dropped items.']
    lines.extend(''.join(row).rstrip() for row in canvas)
    for name, people in occupants.items():
        if name not in civilization.rooms:
            lines.append(f'Unmapped location {name}: '+', '.join(body_for(p)+' '+p.name for p in people))
    return '\n'.join(lines).rstrip()
