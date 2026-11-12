"""Finite, offline civilization mechanics. No generated Python or external services."""
import copy
import math
import random
import re
import shlex
from collections import Counter, defaultdict, deque
import numpy as np
from lonk_dialogue import DialogueGenerator
from lonk_map import render_map


PARAMETERS = ('W1', 'b1', 'W2', 'b2', 'Wv', 'bv')
DEFAULTS = {
    'meme_arousal': 0.65, 'meme_valence': 0.45, 'meme_cooldown': 10, 'max_concepts': 64,
    'annex_population': 4, 'annex_shared_tokens': 3, 'max_annexes': 8,
    'romance_ticks': 4, 'romance_arousal': 0.6, 'birth_cooldown': 40,
    'settlement_ticks': 5, 'city_ticks': 10, 'market_sensitivity': 0.28,
    'max_price_multiplier': 1000.0, 'diffusion_rate': 0.25, 'max_waves': 16,
}


def identity(lonk):
    return getattr(lonk, 'semantic_id', lonk.name)


def key(text):
    return re.sub(r'\s+', ' ', str(text).strip()).lower()


class Civilization:
    COMMANDS = {
        'map': 'Show the live world map, occupants and city growth',
        'society': 'Inspect cultures, annexes, cults and settlements',
        'market': 'Inspect speculative item prices', 'blaspheme': 'Seed a heresy in a quoted holy room',
        'matchmake': 'Link two Lonks romantically', 'heartbreak': 'Break a romance with a rumor',
        'subvert': 'Bribe a Headmaster and schedule a classroom chant',
        'tax': 'Set the broker trade tax (0 to 0.5)', 'confiscate': 'Move a Lonk item into the treasury',
        'back': 'Give replenishing item backing to a Lonk', 'drop': 'Drop a Lonk item into its room',
        'engineer': 'Edit a newborn action bias', 'tune': 'Edit a Chosen action bias and emit diffusion',
    }
    USAGE = {
        'map': '/map',
        'society': '/society', 'market': '/market', 'blaspheme': '/blaspheme "ROOM" RUMOR',
        'matchmake': '/matchmake NAME NAME', 'heartbreak': '/heartbreak NAME [RUMOR]',
        'subvert': '/subvert HEADMASTER ITEM', 'tax': '/tax 0.1', 'confiscate': '/confiscate NAME ITEM',
        'back': '/back NAME ITEM', 'drop': '/drop NAME ITEM', 'engineer': '/engineer BABY ACTION BIAS',
        'tune': '/tune CHOSEN ACTION BIAS',
    }
    def __init__(self, world, territories, factions, item_values, factory):
        self.world, self.factory = world, factory
        self.settings = {**DEFAULTS, **world.config.get('civilization', {})}
        limits = {'meme_arousal': (0, 1), 'meme_valence': (0, 1), 'meme_cooldown': (1, 10000),
                  'max_concepts': (1, 256), 'annex_population': (2, 1000), 'annex_shared_tokens': (1, 1000),
                  'max_annexes': (0, 32), 'romance_ticks': (4, 10000), 'romance_arousal': (0, 1),
                  'birth_cooldown': (1, 10000), 'settlement_ticks': (1, 10000), 'city_ticks': (1, 10000),
                  'market_sensitivity': (0, 1), 'max_price_multiplier': (1, 1000000),
                  'diffusion_rate': (0, 1), 'max_waves': (1, 64)}
        for setting, (low, high) in limits.items():
            value = self.settings[setting]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'civilization.{setting} must be finite and between {low} and {high}')
            if isinstance(DEFAULTS[setting], int) and int(value) != value:
                raise ValueError(f'civilization.{setting} must be an integer')
        self.rooms = {}
        for room in territories:
            self.rooms[room['name']] = {'name': room['name'], 'parent': None,
                'vibe': room.get('description', ''), 'sacred': list(room.get('faction_bonus', {})),
                'level': 0, 'density_ticks': 0, 'dropped': [], 'shrines': [], 'laws': []}
        names = list(self.rooms)
        self.edges = {name: sorted({names[(i - 1) % len(names)], names[(i + 1) % len(names)]} - {name})
                      for i, name in enumerate(names)} if names else {}
        self.factions = {f['name']: {'name': f['name'], 'parent': None} for f in factions}
        self.base_values = {key(name): float(value) for name, value in item_values.items()}
        self.market, self.concepts, self.holy, self.schools = {}, {}, {}, {}
        self.pair_ticks, self.birth_ticks, self.meme_ticks = {}, {}, {}
        self.pending_chants, self.backing, self.waves, self.wars = {}, {}, [], []
        self.power_pool = 0.0
        self.tax_rate = 0.0
        self.treasury = {'coins': 0.0, 'items': []}
        self.last_begin = -1
        self.last_finish = -1
        self.metrics = Counter()

    def living(self):
        return [p for p in self.world.lonks if p.alive]

    def find(self, value):
        return next((p for p in self.living() if key(p.name) == key(value) or identity(p) == value), None)

    def emit(self, text):
        self.world.narrate(text)

    def room(self, name):
        return self.rooms.get(name, {})

    def resolve_room(self, name):
        return next((room for room, data in self.rooms.items()
                     if key(room) == key(name) or key(data.get('display_name', room)) == key(name)), None)

    def root(self, name):
        return self.room(name).get('parent') or name

    def words(self, lonk):
        excluded = DialogueGenerator.WORD_GLUE | set(DialogueGenerator.VERBS)
        excluded |= {w for emotion in DialogueGenerator.EMOTION_WORDS for w in emotion.split()}
        counts = Counter()
        for token, weight in lonk.vocabulary.items():
            for word in re.findall(r'\b[^\W\d_]{3,24}\b', token.lower()):
                if word not in excluded and word != lonk.name.lower():
                    counts[word] += min(100, max(1, int(weight)))
        return counts

    def register_items(self, items):
        for item in items:
            token = key(item['name'])
            base = max(0.01, float(item.get('value', self.base_values.get(token, 1))))
            self.market.setdefault(token, {'name': item['name'], 'base': base, 'alpha': 1.0,
                                           'beta': 1.0, 'mentions': 0, 'promoter': None, 'promoters': {}})

    def price(self, item):
        self.register_items([item])
        record = self.market[key(item['name'])]
        posterior = record['alpha'] / (record['alpha'] + record['beta'])
        limit = max(1.0, float(self.settings['max_price_multiplier']))
        exponent = min(math.log(limit), self.settings['market_sensitivity'] * (record['alpha'] - 1) * posterior)
        return min(1_000_000.0, record['base'] * math.exp(exponent))

    def signal(self, speaker, text, channel):
        if channel not in ('whisper', 'teach', 'scream'):
            return
        for p in self.living():
            self.register_items(p.items)
        for token, record in self.market.items():
            if re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', str(text), re.I):
                record['alpha'] = min(1000.0, record['alpha'] + 1)
                record['mentions'] += 1
                promoters = record.setdefault('promoters', {})
                uid = identity(speaker)
                promoters[uid] = promoters.get(uid, 0) + 1
                if len(promoters) > 64:
                    del promoters[min(promoters, key=promoters.get)]
                record['promoter'] = max(promoters, key=promoters.get)
                self.metrics['market_mentions'] += 1
        for p in self.living():
            p.inventory_value = sum(self.price(item) for item in p.items)

    def apply_concepts(self, lonk):
        applied = set(getattr(lonk, 'cultural_concepts', []))
        for name, axiom in self.concepts.items():
            if name in applied:
                continue
            lonk.vocabulary.setdefault(name, 1)
            lonk.knowledge.add(name)
            lonk.dialogue_generator._remember_phrase(name, lonk.dialogue_generator._learn_words('', None))
            for action, multiplier in axiom['effects'].items():
                lonk.will[action] = min(5.0, lonk.will.get(action, 1.0) * multiplier)
            for combo in lonk.action_weights:
                if combo.split('+')[0] in ('teach', 'give', 'trade'):
                    lonk.action_weights[combo] = min(5.0, lonk.action_weights[combo] * 1.02)
            applied.add(name)
        lonk.cultural_concepts = sorted(applied)

    def breed_memes(self):
        groups = defaultdict(list)
        for p in self.living():
            if p.state[2] >= self.settings['meme_arousal'] and p.state[3] >= self.settings['meme_valence']:
                groups[(p.faction, p.territory)].append(p)
        for (faction, room), peers in groups.items():
            sacred = set(self.room(room).get('sacred', [])) | set(self.room(self.root(room)).get('sacred', []))
            if len(peers) < 2 or faction not in sacred:
                continue
            pair = sorted(peers, key=lambda p: (-sum(self.words(p).values()), p.name))[:2]
            pair_key = '|'.join(sorted(identity(p) for p in pair))
            if self.world.tick - self.meme_ticks.get(pair_key, -100) < self.settings['meme_cooldown']:
                continue
            first = self.words(pair[0]).most_common()
            second = self.words(pair[1]).most_common()
            if not first or not second:
                continue
            a = first[0][0]
            b = next((word for word, _ in second if word != a), second[0][0])
            landmark = self.root(room).split()[-1]
            name = f'The Sacred {a.title()}-{b.title()} {landmark}'
            if name in self.concepts or len(self.concepts) >= self.settings['max_concepts']:
                continue
            effects = {'think': 1.01, 'speak': 1.01, 'trade': 1.01}
            if not any(p.items for p in pair):
                dominant = 'trade'
            elif sum(p.emotion.get('wisdom', 50) for p in pair) >= 120:
                dominant = 'think'
            else:
                curiosity = sum(p.personality.get('curiosity', 50) for p in pair)
                loyalty = sum(p.personality.get('loyalty', 50) for p in pair)
                dominant = 'think' if curiosity > loyalty else 'speak'
            effects[dominant] = 1.04
            self.concepts[name] = {'name': name, 'state': 'canon', 'kind': 'cultural',
                'parents': [identity(p) for p in pair], 'tokens': [a, b], 'room': room,
                'born': self.world.tick, 'effects': effects, 'dominant_action': dominant}
            self.meme_ticks[pair_key] = self.world.tick
            for p in self.living():
                self.apply_concepts(p)
            self.metrics['memes'] += 1
            self.emit(f'LIVE CULTURAL AXIOM: {name} — {pair[0].name} and {pair[1].name} splice a permanent concept.')
            break  # At most one new global axiom per world tick.

    def annexes(self):
        groups = defaultdict(list)
        for p in self.living():
            if not self.room(p.territory).get('parent'):
                groups[(p.faction, p.territory)].append(p)
        for (faction, parent), peers in groups.items():
            if faction is None or len(peers) < self.settings['annex_population']:
                continue
            shared = set(self.words(peers[0]))
            for p in peers[1:]:
                shared &= set(self.words(p))
            if len(shared) < self.settings['annex_shared_tokens']:
                continue
            existing = [r for r in self.rooms.values() if r.get('parent')]
            if len(existing) >= self.settings['max_annexes'] or any(r['parent'] == parent and r.get('faction') == faction for r in existing):
                continue
            token = sorted(shared)[0].title()
            name = f'{parent} / {token} Annex'
            if name in self.rooms:
                continue
            self.rooms[name] = {'name': name, 'parent': parent, 'faction': faction,
                'vibe': 'a bureaucratic annex', 'sacred': [faction], 'level': 0,
                'density_ticks': 0, 'dropped': [], 'shrines': [], 'laws': []}
            self.edges.setdefault(parent, []).append(name)
            self.edges[name] = [parent]
            self.world.config.setdefault('generated_locations', {})[name] = copy.deepcopy(self.rooms[name])
            migrants = max(1, min(2, len(peers) - 3))
            for p in sorted(peers, key=lambda p: p.name)[-migrants:]:
                self.move(p, name, 'annex')
            self.metrics['annexes'] += 1
            self.emit(f'VOID-LEAP ANNEX: {faction} opens {name}; occupants receive two turns per world tick.')

    def extra_turns(self):
        return [p for p in self.living() if self.room(p.territory).get('parent')]

    def move(self, lonk, room, reason='following', target=None):
        if room not in self.rooms or room == lonk.territory:
            return False
        old = lonk.territory
        if old in self.rooms and room not in self.edges.get(old, []):
            return False
        lonk.territory = room
        lonk.location_reason = {'kind': reason, 'place': room, 'target': target, 'from': old}
        self.emit(f'{lonk.name} moves from {old} to {room}.')
        self.on_enter(lonk)
        return True

    def next_room(self, source, target):
        queue = deque([(source, [])])
        seen = {source}
        while queue:
            room, path = queue.popleft()
            if room == target:
                return path[0] if path else target
            for neighbour in self.edges.get(room, []):
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append((neighbour, path + [neighbour]))
        return source

    def on_enter(self, lonk, ritual=True):
        room = self.room(lonk.territory)
        if not room or not hasattr(lonk, 'dialogue_generator'):
            return
        if room.get('level', 0):
            grants = set(getattr(lonk, 'city_blessings', []))
            if lonk.territory not in grants:
                old = getattr(lonk, 'max_health', 100)
                lonk.max_health = min(140, old + 20)
                lonk.health += lonk.max_health - old
                lonk.structural_anxiety_reduction = min(40, getattr(lonk, 'structural_anxiety_reduction', 0) + 10)
                grants.add(lonk.territory)
                lonk.city_blessings = sorted(grants)
        if ritual and room.get('shrines') and getattr(lonk, 'last_shrine_tick', -1) != self.world.tick:
            lonk.last_shrine_tick = self.world.tick
            cult = random.choice(room['shrines'])
            terms = self.factions[cult].get('holy_terms', [cult])
            phrase = ' '.join(random.sample(terms, min(2, len(terms))))
            chant = f'{phrase.title()} is sacred!'
            lonk.dialogue_generator._remember_phrase(chant, lonk.dialogue_generator._learn_words('', None))
            if random.random() < 0.5:
                lonk.last_spoken = chant
                self.emit(f'{lonk.name} screams at the shrine of {cult}: {chant}')
                self.signal(lonk, phrase, 'scream')
            else:
                lonk.trance_until = self.world.tick + 1
                lonk.experience(comfort=2)
                self.emit(f'{lonk.name} enters a holy trance: {chant}')

    def on_death(self, lonk):
        self.pending_chants.pop(identity(lonk), None)
        for survivor in self.living():
            if getattr(survivor, 'romance_partner', None) == identity(lonk):
                self.breakup(survivor, f'{lonk.name} dissolved into dream-mist')
        raw = getattr(lonk, 'last_spoken', '')
        terms = [word for word, _ in self.words(lonk).most_common(2)]
        spoken = [w for w in re.findall(r'\b[^\W\d_]{3,24}\b', raw.lower()) if w not in DialogueGenerator.WORD_GLUE]
        terms = list(dict.fromkeys(spoken[-3:] or terms or [lonk.name.lower()]))
        for term in terms:
            self.holy.setdefault(term, {'martyr': identity(lonk), 'utterance': raw, 'room': lonk.territory, 'tick': self.world.tick})
        susceptible = [p for p in self.living() if p is not lonk and (p.emotion.get('anxiety', 0) >= 65 or p.emotion.get('wisdom', 50) <= 35)]
        if not susceptible:
            return
        name = 'The First Church of ' + ' '.join(terms).title()
        if name not in self.factions and len(self.factions) >= 48:
            return
        if name not in self.factions:
            self.factions[name] = {'name': name, 'parent': lonk.faction, 'holy_terms': terms, 'martyr': identity(lonk)}
            self.metrics['cults'] += 1
        room = self.room(lonk.territory)
        if room:
            if name not in room['shrines']:
                room['shrines'].append(name)
            if name not in room['sacred']:
                room['sacred'].append(name)
        for p in susceptible[:4]:
            p.faction = name
            p.religion = self.cult_religion(name, terms)
        self.emit(f'MARTYRDOM: {lonk.name}\'s last words seed {name}; a shrine rises in {lonk.territory}.')
        for p in self.living():
            if p.territory == lonk.territory:
                self.on_enter(p)

    @staticmethod
    def cult_religion(name, terms):
        return {'name': name, 'sacred_items': list(terms), 'ritual': 'chant',
                'ritual_description': 'chants ' + ' and '.join(terms) + ' at the shrine',
                'description': 'the last words of a departed Lonk are sacred'}

    def pair(self, first, second):
        if first is second:
            raise ValueError('A Lonk needs a different partner')
        for p in (first, second):
            old = self.find(getattr(p, 'romance_partner', ''))
            if old is not None and old not in (first, second):
                old.romance_partner, old.crush = None, None
        first.romance_partner, second.romance_partner = identity(second), identity(first)
        first.crush, second.crush = second.name, first.name
        first.obsession = second.obsession = 0.8
        for person, partner in ((first, second), (second, first)):
            vector = dict(getattr(person, 'affinity_vector', {}))
            vector[identity(partner)] = 0.8
            person.affinity_vector = vector
        self.metrics['crushes'] += 1
        self.emit(f'CRUSH: {first.name} and {second.name} cannot stop thinking about each other.')

    def breakup(self, lonk, rumor):
        partner = self.find(getattr(lonk, 'romance_partner', ''))
        for p in (lonk, partner):
            if p is None:
                continue
            old_partner = getattr(p, 'romance_partner', None)
            if old_partner in getattr(p, 'affinity_vector', {}):
                p.affinity_vector[old_partner] *= 0.1
            p.romance_partner, p.crush, p.obsession = None, None, 0.0
            p.experience(valence=-0.9, trauma=25)
            poem = f'{p.name} dreams: {rumor}; the moss keeps an empty place.'
            p.inner_thoughts.append({'thought': poem, 'tick': self.world.tick, 'kind': 'heartbreak'})
            self.emit(poem)
        self.metrics['heartbreaks'] += 1

    def romance(self):
        peers = self.living()
        current = set()
        for i, first in enumerate(peers):
            for second in peers[i + 1:]:
                pair = '|'.join(sorted((identity(first), identity(second))))
                if first.territory != second.territory:
                    continue
                current.add(pair)
                self.pair_ticks[pair] = self.pair_ticks.get(pair, 0) + 1
                if (not getattr(first, 'romance_partner', None) and not getattr(second, 'romance_partner', None)
                        and self.pair_ticks[pair] >= self.settings['romance_ticks']
                        and min(first.state[2], second.state[2]) >= self.settings['romance_arousal']):
                    self.pair(first, second)
        self.pair_ticks = {p: n for p, n in self.pair_ticks.items() if p in current}

    def births(self):
        seen = set()
        for first in self.living():
            second = self.find(getattr(first, 'romance_partner', ''))
            if second is None or getattr(second, 'romance_partner', None) != identity(first):
                continue
            pair = '|'.join(sorted((identity(first), identity(second))))
            if pair in seen:
                continue
            seen.add(pair)
            room = self.room(first.territory)
            supportive = room.get('level', 0) or re.search(r'support|soft|comfort|warm', room.get('vibe', ''), re.I)
            if (first.territory != second.territory or not supportive
                    or min(first.emotion['joy'], second.emotion['joy']) < 99.99
                    or self.world.tick - self.birth_ticks.get(pair, -1000) < self.settings['birth_cooldown']
                    or len(self.living()) + len(self.world.pending_births) >= self.world.max_population):
                continue
            name = first.name[:max(1, len(first.name) // 2)] + second.name[len(second.name) // 2:]
            occupied = {p.name for p in self.world.lonks + self.world.pending_births}
            stem, suffix = name, 2
            while name in occupied:
                name = stem + str(suffix)
                suffix += 1
            baby = self.factory(name)
            baby.generation = max(first.generation, second.generation) + 1
            baby.parents = [identity(first), identity(second)]
            baby.territory, baby.faction = first.territory, first.faction
            for field in PARAMETERS:
                a, b = getattr(first.brain.nn, field), getattr(second.brain.nn, field)
                setattr(baby.brain.nn, field, (a + b) / 2)
            for field in ('emotion', 'personality'):
                a, b = getattr(first, field), getattr(second, field)
                setattr(baby, field, {word: (a.get(word, 50) + b.get(word, 50)) / 2 for word in a.keys() | b.keys()})
            baby.state = [(a + b) / 2 for a, b in zip(first.state, second.state)]
            origins = {}
            lengths = [len(parent.vocabulary) for parent in (first, second)]
            quota = min(8, *lengths) if all(lengths) else 8
            for parent in (first, second):
                favorites = sorted(parent.vocabulary, key=lambda w: (-parent.vocabulary[w], w))[:quota]
                origins[identity(parent)] = favorites
                for word in favorites:
                    baby.vocabulary[word] = baby.vocabulary.get(word, 0) + parent.vocabulary[word] / 2
                source = getattr(parent, 'wordplay_state', {})
                target = baby.dialogue_generator._learn_words('', None)
                for word, weight in source.get('expressive', {}).items():
                    target['expressive'][word] = max(target['expressive'].get(word, 0), weight)
                    target['words'].setdefault(word, 1)
                for entry in list(source.get('phrases', {}).values())[:8]:
                    baby.dialogue_generator._remember_phrase(entry['text'], target)
            baby.knowledge = set(baby.vocabulary)
            baby.vocabulary_origins = origins
            self.world.pending_births.append(baby)
            self.birth_ticks[pair] = self.world.tick
            self.metrics['births'] += 1
            self.emit(f'A new Lonk is born: {baby.name}! Gen {baby.generation}; parents {first.name} + {second.name}. Use /engineer after arrival to edit its policy bias.')

    def settlements(self):
        population = Counter(p.territory for p in self.living())
        for name, room in list(self.rooms.items()):
            if room.get('parent'):
                continue
            room['density_ticks'] = room.get('density_ticks', 0) + 1 if population[name] >= 3 else 0
            target = 2 if room['density_ticks'] >= self.settings['city_ticks'] or len(room['dropped']) > 10 else 1 if room['density_ticks'] >= self.settings['settlement_ticks'] or len(room['dropped']) > 5 else 0
            if target > room.get('level', 0):
                room['level'] = target
                city = 'The Glittering Metropolis' if 'shiny' in name.lower() else 'The Screaming Citadel' if 'loud' in name.lower() else name + ' Megacity'
                room['display_name'] = city if target == 2 else name + ' Outpost'
                self.metrics['settlements'] += 1
                self.emit(f'SETTLEMENT: {name} grows into {room["display_name"]}.')
                for p in self.living():
                    if p.territory == name:
                        self.on_enter(p)
            if room.get('level'):
                concepts = Counter(c for p in self.living() if p.territory == name for c in getattr(p, 'cultural_concepts', []))
                if concepts:
                    concept = concepts.most_common(1)[0][0]
                    effects = self.concepts.get(concept, {}).get('effects', {'speak': 1})
                    dominant = max(effects, key=effects.get)
                    law = {'trade': 'fair_trade', 'think': 'open_school', 'speak': 'sanctuary'}.get(dominant, 'sanctuary')
                    if room.get('law_source') != concept:
                        room['laws'], room['law_source'] = [law], concept
                        self.emit(f'CITY LAW in {room.get("display_name", name)}: {law}, derived from {concept}.')

    def classrooms(self):
        groups = defaultdict(list)
        for p in self.living():
            if self.room(p.territory).get('level'):
                faction = None if 'open_school' in self.room(p.territory).get('laws', []) else p.faction
                groups[(p.territory, faction)].append(p)
        active = set()
        for (room, faction), peers in sorted(groups.items(), key=lambda row: (-len(row[1]), row[0][0], str(row[0][1]))):
            if len(peers) < 3:
                continue
            if room in active:
                continue
            active.add(room)
            head = max(peers, key=lambda p: (p.emotion.get('wisdom', 50), p.name))
            previous = self.schools.get(room)
            self.schools[room] = {'headmaster': identity(head), 'faction': faction,
                                  'students': [identity(p) for p in peers if p is not head]}
            if not previous or previous['headmaster'] != identity(head):
                self.emit(f'SCHOOL OF THE VOID: {head.name} becomes Headmaster in {room}.')
            for student in peers:
                if student is head:
                    continue
                new = set(head.vocabulary) - set(student.vocabulary)
                student.vocabulary = dict(head.vocabulary)
                student.knowledge = set(head.knowledge)
                student.axioms = copy.deepcopy(head.axioms)
                student.pending_predictions = []
                student.paradigm, student.paradigm_focus = head.paradigm, head.paradigm_focus
                source = getattr(head, 'wordplay_state', {})
                target = student.dialogue_generator._learn_words('', None)
                for field in ('words', 'expressive', 'phrases'):
                    target[field] = copy.deepcopy(source.get(field, {}))
                if new:
                    student.experience(learning=len(new), valence=0.1)
                    self.metrics['school_lessons'] += 1
        self.schools = {r: s for r, s in self.schools.items() if r in active}

    def snapshot(self, lonk):
        return {field: np.array(getattr(lonk.brain.nn, field), dtype=float, copy=True) for field in PARAMETERS}

    def diffuse_edit(self, chosen, before):
        if getattr(chosen, 'wp_role', None) == 'control':
            return
        delta = {field: (np.asarray(getattr(chosen.brain.nn, field)) - before[field]).tolist() for field in PARAMETERS}
        if not any(np.any(value) for value in delta.values()):
            return
        if len(self.waves) >= self.settings['max_waves']:
            self.waves.pop(0)
        self.waves.append({'delta': delta, 'frontier': [chosen.territory], 'seen_rooms': [],
                           'seen_agents': [identity(chosen)], 'distance': 0})
        self.metrics['diffusion_waves'] += 1
        self.emit(f'RESONANT DIFFUSION: edits to {chosen.name} enter the room graph; Control Twins remain isolated.')

    def diffuse(self):
        pending = []
        for wave in self.waves:
            rooms = set(wave['frontier']) - set(wave['seen_rooms'])
            for p in self.living():
                if p.territory not in rooms or identity(p) in wave['seen_agents'] or p.wp_role == 'control':
                    continue
                rate = self.settings['diffusion_rate'] / (1 + wave['distance'])
                for field in PARAMETERS:
                    current = np.asarray(getattr(p.brain.nn, field))
                    delta = np.asarray(wave['delta'][field])
                    if current.shape != delta.shape or not np.all(np.isfinite(delta)):
                        continue
                    value = np.clip(current + rate * delta, -5, 5)
                    setattr(p.brain.nn, field, float(value) if value.ndim == 0 else value)
                wave['seen_agents'].append(identity(p))
                self.metrics['diffused_agents'] += 1
            wave['seen_rooms'] = sorted(set(wave['seen_rooms']) | rooms)
            frontier = {n for room in rooms for n in self.edges.get(room, [])} - set(wave['seen_rooms'])
            if frontier:
                wave['frontier'], wave['distance'] = sorted(frontier), wave['distance'] + 1
                pending.append(wave)
        self.waves = pending

    def intent(self, lonk):
        for p in self.living():
            self.register_items(p.items)
        uid = identity(lonk)
        if uid in self.pending_chants:
            return {'verb': 'proclaim', 'target_type': 'self', 'object': self.pending_chants.pop(uid)}
        if getattr(lonk, 'trance_until', -1) >= self.world.tick:
            return {'verb': 'idle', 'target_type': 'self'}
        partner = self.find(getattr(lonk, 'romance_partner', ''))
        if partner is not None and getattr(lonk, 'obsession', 0.8) >= 0.4:
            if lonk.territory != partner.territory:
                return {'verb': 'follow', 'target_type': 'other', 'target_name': partner.name}
            gifts = [item for item in lonk.items if item.get('romance_gifted_to') not in (uid, identity(partner))]
            if gifts and self.world.tick - getattr(lonk, 'last_romance_gift', -100) >= 3:
                gift = max(gifts, key=self.price)
                return {'verb': 'devote', 'target_type': 'other', 'target_name': partner.name, 'object': gift}
            rivals = [p for p in self.living() if p not in (lonk, partner) and p.territory == lonk.territory and p.personality['aggression'] >= 70]
            if rivals and self.world.tick - getattr(lonk, 'last_jealousy_tick', -100) >= 3:
                lonk.last_jealousy_tick = self.world.tick
                rival = rivals[0]
                lonk.jealousy = {'rival': identity(rival), 'strength': 0.75, 'tick': self.world.tick}
                return {'verb': 'jealous', 'target_type': 'other', 'target_name': rival.name}
        for war in self.wars:
            if war['until'] < self.world.tick or lonk.faction not in war['factions']:
                continue
            enemies = [p for p in self.living() if p.faction in war['factions'] and p.faction != lonk.faction and p.territory == lonk.territory]
            if enemies and random.random() < 0.12:
                return {'verb': 'attack', 'target_type': 'other', 'target_name': enemies[0].name}
        if lonk.personality.get('aggression', 50) >= 70 and lonk.personality.get('loyalty', 50) <= 40:
            targets = [p for p in self.living() if p is not lonk and p.emotion['anxiety'] >= 60 and p.items]
            targets = [p for p in targets if max(self.price(i) for i in p.items) >= 5]
            if targets and random.random() < 0.25:
                target = max(targets, key=lambda p: max(self.price(i) for i in p.items))
                return {'verb': 'seek' if target.territory != lonk.territory else 'extort', 'target_type': 'other', 'target_name': target.name}
        hot = [record for record in self.market.values() if record['mentions'] >= 5]
        if hot:
            lonk.will['trade'] = min(5.0, max(lonk.will.get('trade', 1), 1 + 0.08 * max(r['mentions'] for r in hot)))
            if random.random() < 0.15:
                holders = [p for p in self.living() if p is not lonk and any(self.market[key(i['name'])]['mentions'] >= 5 for i in p.items)]
                if holders:
                    promoters = {record['promoter'] for record in hot}
                    promoted = [p for p in holders if identity(p) in promoters]
                    target = max(promoted or holders, key=lambda p: sum(self.price(i) for i in p.items))
                    return {'verb': 'seek' if target.territory != lonk.territory else 'trade', 'target_type': 'other', 'target_name': target.name}
        return None

    def act(self, lonk, verb, target, obj):
        if verb == 'proclaim':
            lonk.speak(str(obj))
            self.metrics['proclamations'] += 1
            return {'success': True, 'reward': 0.1}
        if target is None:
            return {'success': False, 'reward': -0.02}
        if verb in ('follow', 'seek'):
            destination = self.next_room(lonk.territory, target.territory)
            moved = self.move(lonk, destination, 'following' if verb == 'follow' else 'speculation', target.name)
            return {'success': moved, 'reward': 0.08 if moved else -0.02}
        if verb == 'devote':
            if obj not in lonk.items:
                return {'success': False, 'reward': -0.02}
            obj['romance_gifted_to'] = identity(target)
            lonk.last_romance_gift = self.world.tick
            self.emit(f'{lonk.name} abandons faction business to give {obj["name"]} to their crush {target.name}.')
            return lonk._verb_give(target, obj, 'with love')
        if verb == 'jealous':
            self.emit(f'JEALOUSY: {lonk.name} spreads a vicious rumor about {target.name}.')
            lonk.gossip_about(target, self.find(getattr(lonk, 'romance_partner', '')))
            if random.random() < 0.1 and lonk.personality['aggression'] > 70:
                return lonk._verb_bonk(target, None, 'jealously')
            return {'success': True, 'reward': -0.05}
        if verb == 'extort':
            return {'success': self.extort(lonk, target), 'reward': -0.1}
        return {'success': False, 'reward': -0.02}

    def extort(self, actor, victim):
        if not victim.items or actor.territory != victim.territory or set(self.room(actor.territory).get('laws', [])) & {'sanctuary', 'fair_trade'}:
            return False
        prize = max(victim.items, key=self.price)
        cheap = [item for item in actor.items if self.price(item) <= self.price(prize) * 0.2]
        if not cheap:
            actor.items.append({'name': 'worthless pebble', 'description': 'picked up for a scam', 'value': 0, 'shiny': False})
            actor.inventory = [i['name'] for i in actor.items]
            self.emit(f'{actor.name} picks up a worthless pebble and sizes up {victim.name}\'s {prize["name"]}.')
            return False
        probability = min(0.95, max(0.05, victim.emotion['anxiety'] / 100 + actor.personality['aggression'] / 250 - victim.personality['loyalty'] / 300))
        if random.random() >= probability:
            self.emit(f'{victim.name} refuses {actor.name}\'s intimidation trade.')
            return False
        offer = min(cheap, key=self.price)
        actor.items.remove(offer); victim.items.remove(prize)
        actor.items.append(prize); victim.items.append(offer)
        actor.inventory = [i['name'] for i in actor.items]
        victim.inventory = [i['name'] for i in victim.items]
        victim.experience(valence=-0.6, trauma=4)
        victim.update_relationship(actor, -15)
        self.metrics['scams'] += 1
        self.emit(f'{actor.name} scammed {victim.name}! Swapped {offer["name"]} for {prize["name"]}.')
        return True

    def trade(self, actor, other):
        if not other.items or actor is other or actor.territory != other.territory:
            return False
        if not actor.items:
            affordable = [item for item in other.items if self.price(item) <= actor.coins]
            if not affordable:
                return False
            bought = max(affordable, key=self.price)
            price = self.price(bought)
            actor.coins -= price; other.coins += price
            other.items.remove(bought); actor.items.append(bought)
            tax = min(other.coins, price * self.tax_rate)
            other.coins -= tax; self.treasury['coins'] += tax
            for p in (actor, other):
                p.inventory = [item['name'] for item in p.items]
                p.inventory_value = sum(self.price(item) for item in p.items)
                p.experience(valence=0.2)
            self.metrics['cash_trades'] += 1
            self.emit(f'MARKET PURCHASE: {actor.name} pays {price:.2f} coins to {other.name} for {bought["name"]}.')
            return True
        candidates = []
        for mine in actor.items:
            for theirs in other.items:
                a, b = self.price(mine), self.price(theirs)
                difference = b - a
                if abs(difference) <= max(a, b) * 0.25 or (difference > 0 and actor.coins >= difference) or (difference < 0 and other.coins >= -difference):
                    candidates.append((abs(difference), mine, theirs, difference))
        if not candidates:
            # Use the existing item-to-coins conversion instead of either
            # accepting an unfair barter or remaining permanently cashless.
            liquidated = min(actor.items, key=self.price)
            value = self.price(liquidated)
            actor.convert_to_coins(liquidated['name'])
            self.metrics['monetized_items'] += 1
            self.emit(f'{actor.name} declines an unfair barter and converts {liquidated["name"]} into {value:.2f} coins for a later purchase.')
            return False
        _, mine, theirs, difference = min(candidates, key=lambda row: row[0])
        if abs(difference) > max(self.price(mine), self.price(theirs)) * 0.25:
            actor.coins -= difference; other.coins += difference
        actor.items.remove(mine); other.items.remove(theirs)
        actor.items.append(theirs); other.items.append(mine)
        for trader, received in ((actor, theirs), (other, mine)):
            tax = min(trader.coins, self.price(received) * self.tax_rate)
            trader.coins -= tax; self.treasury['coins'] += tax
            trader.inventory = [i['name'] for i in trader.items]
            trader.inventory_value = sum(self.price(item) for item in trader.items)
            trader.experience(valence=0.3)
        self.metrics['trades'] += 1
        self.emit(f'TRADE: {actor.name} exchanges {mine["name"]} for {other.name}\'s {theirs["name"]} at market prices.')
        return True

    def begin_tick(self):
        if self.last_begin == self.world.tick:
            return
        self.last_begin = self.world.tick
        for p in self.living():
            self.register_items(p.items)
            p.inventory_value = sum(self.price(item) for item in p.items)
            self.apply_concepts(p)
            partner = self.find(getattr(p, 'romance_partner', ''))
            if partner is not None:
                vector = dict(getattr(p, 'affinity_vector', {}))
                score = vector.get(identity(partner), getattr(p, 'obsession', 0.8))
                vector[identity(partner)] = min(1.0, max(0.4, score + (0.03 if p.territory == partner.territory else -0.005)))
                p.affinity_vector = vector
                p.obsession = vector[identity(partner)]
            supply = self.backing.get(identity(p))
            if supply and not any(key(i['name']) == key(supply['name']) for i in p.items):
                p.items.append(copy.deepcopy(supply))
                p.inventory = [i['name'] for i in p.items]
            if self.room(p.territory).get('level'):
                self.on_enter(p, ritual=False)
                p.emotion['anxiety'] = max(0, p.emotion['anxiety'] - 10)
            if self.room(p.territory).get('parent'):
                fuel = next((i for i in p.items if re.search(r'\b(?:egg|portal)\b', i['name'], re.I)), None)
                if fuel:
                    p.items.remove(fuel)
                    p.inventory = [i['name'] for i in p.items]
                    p.structural_anxiety_reduction = min(40, getattr(p, 'structural_anxiety_reduction', 0) + 2)
                    self.power_pool = min(100, self.power_pool + 5)
                    self.metrics['annex_fuel'] += 1
                    self.emit(f'{p.name} consumes {fuel["name"]} in the annex: structural Anxiety falls; Power enters the world loop.')
            power = min(2.0, self.power_pool / max(1, len(self.living())))
            p.emotion['power'] = min(100, p.emotion['power'] + power)
            p.state[0] = min(1, p.state[0] + power / 100)
        self.power_pool *= 0.8
        for record in self.market.values():
            record['alpha'] = 1 + (record['alpha'] - 1) * 0.99
            record['beta'] = min(1000, record['beta'] + 0.05)
        self.romance()
        self.births()
        self.diffuse()

    def finish_tick(self):
        if self.last_finish == self.world.tick:
            return
        self.last_finish = self.world.tick
        self.breed_memes()
        self.annexes()
        self.settlements()
        self.classrooms()
        self.wars = [war for war in self.wars if war['until'] >= self.world.tick]

    def command(self, command, raw):
        args = shlex.split(raw)
        required = {'map': 0, 'society': 0, 'market': 0, 'tax': 1, 'matchmake': 2, 'heartbreak': 1,
                    'blaspheme': 2, 'subvert': 2, 'engineer': 3, 'tune': 3, 'back': 2,
                    'drop': 2, 'confiscate': 2}
        if command not in required or len(args) < required[command]:
            raise ValueError('Usage: ' + self.USAGE.get(command, '/help'))
        if command == 'map':
            return render_map(self)
        if command == 'society':
            overview = f'Civilization: {len(self.concepts)} Live Cultural Axioms; {len(self.holy)} Holy terms; {sum(bool(r.get("parent")) for r in self.rooms.values())} annexes; {len(self.schools)} schools; {dict(self.metrics)}'
            details = [f'  CANON: {name}' for name in list(self.concepts)[-8:]]
            details += [f'  {room.get("display_name", name)} [{name}] | level {room.get("level", 0)} | laws {room.get("laws", [])}'
                        for name, room in self.rooms.items() if room.get('level') or room.get('parent')]
            for room, school in self.schools.items():
                head = self.find(school['headmaster'])
                details.append(f'  SCHOOL {room}: Headmaster {head.name if head else "departed"}; {len(school["students"])} students')
            details += [f'  SHRINE {name}: {", ".join(room["shrines"])}' for name, room in self.rooms.items() if room.get('shrines')]
            return '\n'.join([overview] + details)
        if command == 'market':
            return '\n'.join(f'{record["name"]}: {self.price({"name": record["name"], "value": record["base"]}):.2f} | mentions {record["mentions"]}' for record in self.market.values()) or 'No items registered yet.'
        if command == 'tax':
            rate = float(args[0])
            if not math.isfinite(rate) or not 0 <= rate <= 0.5:
                raise ValueError('Tax must be between 0 and 0.5')
            self.tax_rate = rate
            return f'Trade tax set to {rate:.0%}.'
        if command == 'matchmake':
            first, second = (self.find(name) for name in args[:2])
            if first is None or second is None:
                raise ValueError('Both Lonks must be alive')
            self.pair(first, second)
            return 'Matchmaking applied.'
        if command == 'heartbreak':
            lonk = self.find(args[0])
            if lonk is None:
                raise ValueError('Lonk not found')
            self.breakup(lonk, ' '.join(args[1:]) or 'a rumor of betrayal')
            return 'The rumor fractures the romance.'
        if command == 'blaspheme':
            room = self.resolve_room(args[0])
            if room is None:
                raise ValueError('Quote the full room name')
            cults = self.room(room).get('shrines', [])
            if not cults:
                return 'There is no shrine here to split.'
            if len(self.factions) >= 48:
                return 'Faction limit reached.'
            parent = cults[0]
            rumor = ' '.join(args[1:]) or 'the shrine is wrong'
            name = parent + ' / Heresy of ' + ' '.join(re.findall(r'\w+', rumor)[-2:]).title()
            self.factions[name] = {'name': name, 'parent': parent, 'holy_terms': [rumor], 'heretical': True}
            if name not in self.rooms[room]['sacred']:
                self.rooms[room]['sacred'].append(name)
            if name not in self.rooms[room]['shrines']:
                self.rooms[room]['shrines'].append(name)
            followers = [p for p in self.living() if p.territory == room and p.faction == parent]
            for p in followers:
                p.hear('Player', rumor, is_player=True)
            for p in followers[::2]:
                p.faction = name
                p.heretic = True
                p.religion = self.cult_religion(name, [rumor])
            self.wars = [war for war in self.wars if set(war['factions']) != {parent, name}][-31:]
            self.wars.append({'factions': [parent, name], 'until': self.world.tick + 30, 'reason': rumor})
            self.metrics['schisms'] += 1
            self.emit(f'HERESY: {name} rejects {parent}; a civil war begins over "{rumor}".')
            return 'Schism recorded.'
        if command == 'subvert':
            head = self.find(args[0])
            school = next((s for s in self.schools.values() if head and s['headmaster'] == identity(head)), None)
            if school is None:
                raise ValueError('Name an active Headmaster')
            head.receive_gift(' '.join(args[1:]) or 'pickle')
            phrase = 'I am Pickle Rick!'
            head.dialogue_generator._remember_phrase(phrase, head.dialogue_generator._learn_words('', None))
            for uid in [identity(head)] + school['students']:
                self.pending_chants[uid] = phrase
            return 'The classroom will chant on its next turn.'
        lonk = self.find(args[0]) if args else None
        if lonk is None:
            raise ValueError('Lonk not found')
        if command in ('engineer', 'tune'):
            if command == 'engineer' and (lonk.generation < 2 or lonk.age > 1):
                raise ValueError('Engineering is available for newborns through age 1')
            if lonk.wp_role == 'control':
                raise ValueError('The Control Twin is excluded from developer weight edits')
            if command == 'tune' and lonk.wp_role != 'chosen':
                raise ValueError('/tune targets the Chosen Lonk; /engineer targets newborns')
            action, value = args[1], float(args[2])
            if action not in lonk.ACTIONS or not math.isfinite(value) or not -5 <= value <= 5:
                raise ValueError('Use an action name and a finite bias from -5 to 5')
            before = self.snapshot(lonk)
            lonk.brain.nn.b2[lonk.ACTIONS.index(action)] = value
            if lonk.wp_role == 'chosen':
                self.diffuse_edit(lonk, before)
            return f'{lonk.name}: birth policy bias for {action} set to {value}.'
        if command == 'back':
            item = ' '.join(args[1:]) or 'portal'
            supply = {'name': item, 'description': 'supplied by the interdimensional broker', 'value': 10, 'shiny': True}
            self.backing[identity(lonk)] = supply
            lonk.receive_gift(item)
            return f'{lonk.name} now has replenishing backing in {item}.'
        item_name = key(' '.join(args[1:]))
        item = next((i for i in lonk.items if key(i['name']) == item_name), None)
        if item is None:
            raise ValueError('That item is not in their inventory')
        if command in ('confiscate', 'drop'):
            lonk.items.remove(item)
            lonk.inventory = [i['name'] for i in lonk.items]
            if command == 'drop':
                self.room(lonk.territory)['dropped'].append(item)
            else:
                self.treasury['items'].append(item)
            return f'{item["name"]} {"dropped in the room" if command == "drop" else "confiscated by the broker"}.'
        raise ValueError('Unknown civilization command')

    def to_dict(self):
        fields = ('settings', 'rooms', 'edges', 'factions', 'market', 'concepts', 'holy', 'schools',
                  'pair_ticks', 'birth_ticks', 'meme_ticks', 'pending_chants', 'backing', 'waves',
                  'wars', 'power_pool', 'tax_rate', 'treasury', 'last_begin', 'last_finish', 'metrics')
        return {field: copy.deepcopy(dict(getattr(self, field)) if field == 'metrics' else getattr(self, field)) for field in fields}

    def restore(self, data):
        if not data:
            return
        for field in self.to_dict():
            if field in data:
                setattr(self, field, copy.deepcopy(data[field]))
        self.metrics = Counter(self.metrics)
        self.world.config['generated_locations'] = {name: copy.deepcopy(room) for name, room in self.rooms.items() if room.get('parent')}
