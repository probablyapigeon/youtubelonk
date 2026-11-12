"""Small compositional dialogue grammar. No model, service, or network access.

This deliberately handles a limited grammar rather than claiming to understand
arbitrary English. Facts are attributed to the speaker, not invented as world events.
"""
import random
import re
from collections import Counter
import copy
from lonk_semantics import SemanticTrace, compress
from lonk_visuals import learn_emojis, express_emojis


class DialogueGenerator:
    EMOTION_WORDS = set('sad happy curious calm nervous angry afraid tired lonely peaceful joyful excited'.split())
    # Inflection data, not complete response sentences.
    VERBS = {
        'like': ('likes', 'liked'), 'love': ('loves', 'loved'),
        'hate': ('hates', 'hated'), 'want': ('wants', 'wanted'),
        'need': ('needs', 'needed'), 'find': ('finds', 'found'),
        'have': ('has', 'had'), 'lose': ('loses', 'lost'),
        'see': ('sees', 'saw'), 'take': ('takes', 'took'),
        'steal': ('steals', 'stole'), 'eat': ('eats', 'ate'),
        'learn': ('learns', 'learned'), 'teach': ('teaches', 'taught'),
        'bonk': ('bonks', 'bonked'), 'hurt': ('hurts', 'hurt'),
        'attack': ('attacks', 'attacked'), 'help': ('helps', 'helped'),
        'know': ('knows', 'knew'), 'feel': ('feels', 'felt'),
    }
    COLORS = set('red blue green yellow purple pink orange white black gray grey gold silver brown'.split())
    WORD_GLUE = set(('a an the i you he she it we they me my your our their his her '
                     'this that these those am is are was were be been being do does did '
                     'not no yes and or but if then of to for from with in on at by about '
                     'what who why where when how which can could would should will shall '
                     'have has had very more most some any just still also really so as '
                     'hello hi hey greetings word words mean means teach please say said '
                     'today yesterday nothing something anything everything').split())

    def __init__(self, lonk_ref=None):
        self.lonk = lonk_ref
        self._standalone_memory = {}
        self._standalone_wordplay = {}
        self.trace = SemanticTrace()

    @staticmethod
    def _external_speaker(name):
        return name == 'Player' or str(name).startswith('YouTube:')

    def _learn_words(self, text, source='Player'):
        """Learn ordinary words and swears alike, without a special swear list."""
        if self.lonk is None:
            state = self._standalone_wordplay
        else:
            if not hasattr(self.lonk, 'wordplay_state'):
                self.lonk.wordplay_state = {}
            state = self.lonk.wordplay_state
        state['turn'] = state.get('turn', 0) + 1
        words = state.setdefault('words', {})
        expressive = state.setdefault('expressive', {})
        if state.get('lexicon_version', 0) < 2:
            # Old saves mixed the grammar's own nouns into the swear slots.
            # Recover explicit lessons without erasing factual vocabulary.
            history = getattr(self.lonk, 'memory', {})
            lessons = [e.get('message', '') for e in history.get('player_interactions', [])]
            previous = history.get('player_words', [])
            if len(previous) <= 2:
                lessons.extend(previous)
            for lesson in lessons:
                token = str(lesson).lower().strip(' .!?')
                if re.fullmatch(r'[^\W\d_]{2,24}', token) and token not in self.WORD_GLUE:
                    expressive[token] = 1
            state['lexicon_version'] = 2
            if state.get('pending_word') not in expressive:
                state.pop('pending_word', None)
        excluded = self.WORD_GLUE | set(self.VERBS)
        excluded.update(form for forms in self.VERBS.values() for form in forms)
        if self.lonk is not None:
            excluded.add(self.lonk.name.lower())
            world = getattr(self.lonk, 'world', None)
            excluded.update(lonk.name.lower() for lonk in getattr(world, 'lonks', []))
            # Existing saves already contain words taught before this feature.
            old_words = getattr(self.lonk, 'memory', {}).get('player_words', [])
            for word in old_words:
                word = word.lower().strip('.,!?"\'()')
                if re.fullmatch(r'[^\W\d_]{2,24}', word) and word not in excluded:
                    words.setdefault(word, 1)
        for word in re.findall(r'\b[^\W\d_]{2,24}\b', text.lower()):
            if word not in excluded:
                words[word] = min(20, words.get(word, 0) + 1)
        taught = []
        if self._external_speaker(source):
            lesson = re.fullmatch(r'(?:the word |learn |say )?([^\W\d_]{2,24})', text.lower().strip(' .!?'))
            if lesson and lesson[1] not in excluded:
                taught.append(lesson[1])
            address = re.fullmatch(r'(?:how are you|how do you feel)[, ]+(\w+)', text.lower().strip(' .!?'))
            if address and address[1] not in excluded and address[1] not in self.EMOTION_WORDS:
                taught.append(address[1])
            modifier = re.search(r'\bfeel (\w+) (\w+)\b', text, re.I)
            if modifier and modifier[2].lower() in self.EMOTION_WORDS | {'love', 'peace'} and modifier[1].lower() not in excluded:
                taught.append(modifier[1].lower())
        elif source:
            # Copy expressive usage, not every ordinary noun in a peer's line.
            match = re.search(r'^(?:what|where|when|why|how|who) the (\w+)\b', text, re.I)
            feeling = re.fullmatch(r'I feel (\w+)(?: .+)?', text, re.I)
            interjection = re.match(r'^(\w+)[.!]\s', text)
            single = re.fullmatch(r'(\w+)', text)
            for candidate in (match, feeling, interjection, single):
                if candidate:
                    token = candidate[1].lower()
                    if token not in excluded and token not in self.EMOTION_WORDS:
                        world = getattr(self.lonk, 'world', None)
                        peer = next((p for p in getattr(world, 'lonks', []) if p.name == source), None)
                        if peer is None or token in getattr(peer, 'wordplay_state', {}).get('expressive', {}):
                            taught.append(token)
        for word in taught:
            if word in words:
                if word not in expressive:
                    state['pending_word'] = word
                expressive[word] = min(20, expressive.get(word, 0) + 1)
        if len(words) > 128:
            keep = sorted(words, key=lambda word: words[word], reverse=True)[:128]
            state['words'] = {word: words[word] for word in keep}
        return state

    def _wordplay(self, reply, state):
        """Try a learned word in a grammatical slot, sometimes the wrong one."""
        phrases = state.get('phrases', {})
        words = dict(state.get('expressive', {}))
        words.update({key: entry['count'] for key, entry in phrases.items()})
        candidates = [word for word in words if not re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', reply, re.I)]
        if not candidates:
            return reply
        pending = state.get('pending_phrase') or state.get('pending_word')
        fresh = pending in candidates
        playful = getattr(self.lonk, 'personality', {}).get('playfulness', 50)
        if not fresh and random.random() >= 0.15 + playful / 400:
            return reply
        if not fresh:
            candidates = [w for w in candidates if w != state.get('last_word')] or candidates
        uses = state.setdefault('uses', {})
        weights = [words[w] / (1 + uses.get(w, 0)) for w in candidates]
        key = pending if fresh else random.choices(candidates, weights=weights, k=1)[0]
        word = phrases[key]['text'] if key in phrases else key
        feeling = re.fullmatch(r'I feel (.+)\.', reply)
        need = re.fullmatch(r'I need (.+)\.', reply)
        if key in phrases:
            # Whole sayings remain whole, rather than becoming scrambled nouns.
            reply = word.rstrip('.!?') + '! ' + reply
        elif feeling:
            # The engine knows sentence structure before it knows every word's
            # part of speech: a new noun may accidentally become a feeling.
            complement = word if random.random() < 0.5 else word + ' ' + feeling[1]
            reply = self._sentence('I feel ' + complement)
        elif need:
            article = 'an' if word[0] in 'aeiou' else 'a'
            complement = article + ' ' + word if random.random() < 0.5 else word + ' ' + need[1]
            reply = self._sentence('I need ' + complement)
        elif re.match(r'^(What|Where|When|Why|How|Who)\b', reply):
            first, rest = reply.split(' ', 1)
            reply = first + ' the ' + word + ' ' + rest
        else:
            reply = self._sentence(word) + ' ' + reply
        uses[key] = uses.get(key, 0) + 1
        state['last_word'], state['last_turn'] = key, state['turn']
        if fresh:
            state.pop('pending_phrase' if key in phrases else 'pending_word', None)
        return reply

    @staticmethod
    def _remember_phrase(phrase, state):
        phrase = re.sub(r'\s+', ' ', phrase).strip(' .!?;,:"')[:100]
        key = phrase.lower()
        phrases = state.setdefault('phrases', {})
        fresh = key not in phrases
        entry = phrases.setdefault(key, {'text': phrase, 'count': 0})
        entry['count'] = min(20, entry['count'] + 1)
        if fresh:
            state['pending_phrase'] = key
        if len(phrases) > 32:
            victim = min((p for p in phrases if p != key), key=lambda p: phrases[p]['count'])
            del phrases[victim]
        return entry['text']

    def _learn_phrase(self, text, state):
        """Learn a bounded saying, preferring repeated chunks of a long message."""
        chunks = [re.findall(r"[\w]+(?:['\u2019][\w]+)*", clause)
                  for clause in re.split(r'[.!?;\n]+', text)]
        occurrences, originals = Counter(), {}
        for tokens in chunks:
            for size in range(3, min(8, len(tokens)) + 1):
                for offset in range(len(tokens) - size + 1):
                    part = tokens[offset:offset + size]
                    if part[0].lower() in self.WORD_GLUE or part[-1].lower() in self.WORD_GLUE:
                        continue
                    key = ' '.join(part).lower()
                    occurrences[key] += 1
                    originals[key] = ' '.join(part)
        repeated = [key for key, count in occurrences.items() if count > 1]
        if repeated:
            key = max(repeated, key=lambda p: (occurrences[p] * len(p.split()), len(p)))
            phrase = originals[key]
        else:
            short = [' '.join(tokens) for tokens in chunks if 3 <= len(tokens) <= 8]
            if short:
                phrase = short[0]
            else:
                tokens = next((tokens for tokens in chunks if len(tokens) >= 3), [])
                phrase = ' '.join(tokens[:8])
        if not phrase:
            return None
        # A short multi-sentence saying can contribute more than its first line.
        others = [' '.join(tokens) for tokens in chunks if 3 <= len(tokens) <= 8
                  and ' '.join(tokens).lower() != phrase.lower()]
        for other in list(dict.fromkeys(others))[:3]:
            self._remember_phrase(other, state)
        return self._remember_phrase(phrase, state)

    def _inherit_phrases(self, text, state, partner):
        world = getattr(self.lonk, 'world', None)
        peer = next((p for p in getattr(world, 'lonks', []) if p.name == partner), None)
        if peer is not None:
            for key, entry in getattr(peer, 'wordplay_state', {}).get('phrases', {}).items():
                if re.search(r'(?<!\w)' + re.escape(key) + r'(?!\w)', text, re.I):
                    self._remember_phrase(entry['text'], state)

    def _experiment(self, word, state):
        """Try a newly heard word instead of demanding its definition."""
        verb = random.choice(('feel', 'need', 'learn', 'want'))
        if verb == 'feel':
            reply = self._sentence('I feel ' + word)
        elif verb == 'need':
            article = 'an' if word[0].lower() in 'aeiou' else 'a'
            reply = self._sentence('I need ' + article + ' ' + word)
        else:
            reply = self._sentence('can I ' + verb + ' ' + word, True)
        uses = state.setdefault('uses', {})
        uses[word] = uses.get(word, 0) + 1
        state['last_word'], state['last_turn'] = word, state['turn']
        return reply

    def adapt_spoken_line(self, line):
        """Let explicit dreams and combat remarks share the learned vocabulary."""
        return self._wordplay(line, self._learn_words('', source=None))

    @staticmethod
    def _sentence(text, question=False):
        text = re.sub(r'\s+', ' ', text).strip(' .!?')
        return text[:1].upper() + text[1:] + ('?' if question else '.')

    @staticmethod
    def _clean(text):
        text = str(text or '').strip()
        # Old saves contain dialogue with the speaker label inside the message.
        text = re.sub(r'^\w+:\s*', '', text)
        # A greeting may be followed by a real contribution in the same turn.
        text = re.sub(r'^(?:hello|hi|hey),?\s+[\w-]+[.!]\s*', '', text, flags=re.I)
        text = text.replace('\u2019', "'")
        for short, full in {"I'm": 'I am', "i'm": 'I am', "don't": 'do not',
                            "doesn't": 'does not', "didn't": 'did not',
                            "it's": 'it is', "you're": 'you are'}.items():
            text = re.sub(r'\b' + re.escape(short) + r'\b', full, text, flags=re.I)
        return text.strip(' .!?')

    def _memory(self, partner):
        if self.lonk is None:
            memories = self._standalone_memory
        else:
            if not hasattr(self.lonk, 'dialogue_state'):
                self.lonk.dialogue_state = {}
            memories = self.lonk.dialogue_state
        if partner not in memories:
            if len(memories) >= 50:
                viewers = [key for key in memories if str(key).startswith('YouTube:')]
                del memories[viewers[0] if viewers else next(iter(memories))]
            memories[partner] = {'topic': '', 'referent': '', 'facts': [], 'last_reply': '', 'turn': 0}
        return memories[partner]

    @staticmethod
    def _view(text, partner):
        """Translate an incoming speaker's pronouns into the listener's reply."""
        words = {'i': 'you', 'me': 'you', 'my': 'your', 'mine': 'yours',
                 'you': 'I', 'your': 'my', 'yours': 'mine', 'myself': 'yourself'}
        return re.sub(r"\b(?:I|me|my|mine|you|your|yours|myself)\b",
                      lambda m: words[m.group().lower()], text, flags=re.I)

    def _parse(self, text, partner, memory):
        # Keep clause structure instead of sampling arbitrary vocabulary tokens.
        forms = {form: (base, 'past' if form == past else 'present')
                 for base, (third, past) in self.VERBS.items()
                 for form in (base, third, past)}
        verbs = '|'.join(sorted(forms, key=len, reverse=True))
        match = re.fullmatch(r'(?P<subject>I|you|we|they|he|she|it|[A-Z][\w-]*)\s+'
                             r'(?:(?:also|still|really|actually|just)\s+)*'
                             r'(?:(?P<aux>do|does|did|can|could)\s+)?(?P<not>not\s+)?'
                             r'(?P<verb>' + verbs + r')\s+(?P<object>.+)', text, re.I)
        if not match:
            return None
        subject = match['subject']
        subject = partner if subject.lower() == 'i' else subject
        subject = getattr(self.lonk, 'name', 'Lonk') if subject.lower() == 'you' else subject
        if subject.lower() == 'it' and memory['topic']:
            subject = memory['topic']
        base, tense = forms[match['verb'].lower()]
        if match['aux']:
            tense = 'past' if match['aux'].lower() == 'did' else 'present'
        obj = self._view(match['object'], partner)
        if obj.lower() in ('it', 'that', 'this') and memory.get('referent'):
            obj = memory['referent']
        return {'subject': subject, 'verb': base, 'object': obj,
                'tense': tense, 'negative': bool(match['not']),
                'modal': match['aux'].lower() if match['aux'] and match['aux'].lower() in ('can', 'could') else None}

    def _clause(self, fact, partner):
        subject = fact['subject']
        if subject == partner:
            subject = 'you'
        elif self.lonk and subject == self.lonk.name:
            subject = 'I'
        base = fact['verb']
        third, past = self.VERBS[base]
        plural = subject.lower() in ('i', 'you', 'we', 'they')
        if fact.get('modal'):
            verb = fact['modal'] + (' not ' if fact['negative'] else ' ') + base
        elif fact['negative']:
            aux = 'did' if fact['tense'] == 'past' else ('do' if plural else 'does')
            verb = aux + ' not ' + base
        else:
            verb = past if fact['tense'] == 'past' else (base if plural else third)
        adjuncts = [fact[key] for key in ('place', 'time') if fact.get(key)]
        return self._sentence(' '.join((subject, verb, fact['object'], *adjuncts)))

    def _state(self):
        lonk = self.lonk
        if lonk is None:
            return self._sentence('I am listening')
        emotion = getattr(lonk, 'emotion', {})
        if getattr(lonk, 'health', 100) < 40:
            return self._sentence('I need help with my injuries')
        brain = getattr(lonk, 'brain', None)
        if brain is not None and getattr(brain, 'state_vec', None) is not None:
            feeling = brain.get_emotional_state()
        elif emotion.get('anxiety', 0) > 65:
            feeling = 'nervous'
        elif emotion.get('joy', 50) < 30:
            feeling = 'sad'
        elif emotion.get('joy', 50) > 70:
            feeling = 'happy'
        else:
            feeling = 'curious' if getattr(lonk, 'personality', {}).get('curiosity', 50) > 60 else 'calm'
        return self._sentence('I feel ' + feeling)

    def _question_about(self, fact, partner, turn):
        subject = 'you' if fact['subject'] == partner else fact['subject']
        obj, verb = fact['object'], fact['verb']
        if self.lonk and subject == self.lonk.name:
            # A reported accusation is not evidence of an action or its motive.
            return self._sentence('what happened to ' + obj, True)
        plural = subject.lower() in ('you', 'i', 'we', 'they')
        aux = 'did' if fact['tense'] == 'past' else ('do' if plural else 'does')
        if fact['negative'] and verb in ('like', 'love', 'want'):
            return self._sentence('what bothers ' + ('you' if subject == 'you' else subject) + ' about ' + obj, True)
        if verb == 'feel':
            return self._sentence('what made ' + subject + ' feel ' + obj, True)
        if verb in ('like', 'love', 'hate'):
            return self._sentence('what ' + aux + ' ' + subject + ' ' + verb + ' about ' + obj, True)
        if verb in ('find', 'see', 'lose', 'eat', 'learn', 'take', 'steal'):
            question = 'where' if turn % 2 else 'when'
        elif verb in ('bonk', 'hurt', 'attack', 'help'):
            question = 'why'
        elif verb in ('need', 'want'):
            question = 'why'
        else:
            question = 'how'
        return self._sentence(' '.join((question, aux, subject, verb, obj)), True)

    def _contribution(self, memory, avoid=()):
        """Offer current information instead of asking another generic question."""
        candidates = [('mood', self._state())]
        lonk = self.lonk
        place = getattr(lonk, 'territory', None)
        if place:
            candidates.append(('location', self._sentence('I am in ' + place)))
        for item in getattr(lonk, 'items', [])[-3:]:
            name = item.get('name', 'something') if isinstance(item, dict) else str(item)
            candidates.append(('item:' + name, self._sentence('I have ' + name)))
        brain = getattr(lonk, 'brain', None)
        if brain is not None:
            need = brain.get_need(lonk)
            if need not in ('idle', 'items', 'territory'):
                candidates.append(('need', self._sentence('I need ' + need)))
        recent = memory.setdefault('recent_contributions', [])
        fresh = [(key, text) for key, text in candidates if text.casefold() not in avoid]
        candidates = fresh or candidates
        options = [(key, text) for key, text in candidates if key not in recent[-2:]] or candidates
        key, reply = random.choice(options)
        recent.append(key)
        del recent[:-4]
        return reply

    def _place_response(self, place, memory):
        """Use a complete place referent and known descriptions, not its last word."""
        memory['topic'] = memory['referent'] = place
        config = getattr(getattr(self.lonk, 'world', None), 'config', {})
        places = config.get('territories', {})
        detail = places.get(place, {}) if isinstance(places, dict) else {}
        description = detail.get('vibe') or detail.get('description')
        if description:
            description = str(description)
            if description.lower().startswith(('the ', 'a ', 'an ')) or re.search(r'\b(?:makes|yells|sings|moves|stares|is|are)\b', description):
                located = re.sub(r'\bhere\b', 'in ' + place, description)
                return self._sentence(located if located != description else description + ' in ' + place)
            if re.match(r'^(?:glimmers|rustles|hums|glows|smells)\b', description, re.I):
                return self._sentence(place + ' ' + description)
            return self._sentence(place + ' feels ' + description)
        if place == getattr(self.lonk, 'territory', None):
            return self._sentence('I am in ' + place) + ' ' + self._state()
        return self._sentence('I want to visit ' + place)

    def _location_reason(self, place=None):
        current = getattr(self.lonk, 'territory', None)
        if place and current and place.lower() != current.lower():
            return self._sentence('I am in ' + current)
        arrival = getattr(self.lonk, 'location_reason', None)
        if arrival and arrival.get('place') == current:
            if arrival.get('kind') == 'following' and arrival.get('target'):
                return self._sentence('I followed ' + arrival['target'] + ' to ' + current)
            if arrival.get('kind') in (None, 'wandering'):
                return self._sentence('I wandered into ' + current)
            return self._sentence('I moved to ' + current)
        return self._sentence('I do not remember why I came to ' + current) if current else self._sentence('I do not know where I am')

    def generate_response(self, message=None, context='statement', target=None):
        partner = getattr(target, 'name', target) or 'Player'
        memory = self._memory(str(partner))
        before = copy.deepcopy(memory)
        raw_input = str(message) if message is not None else None
        interpretation = compress(raw_input or '', str(partner), getattr(self.lonk, 'name', 'Lonk'),
                                  self._clean, self._parse, memory)
        if raw_input is None:
            interpretation['coverage'] = 'spontaneous'
        text = self._clean(message)
        wordplay = self._learn_words(text, source=str(partner))
        learn_emojis(raw_input or '', wordplay)
        if not self._external_speaker(partner):
            self._inherit_phrases(text, wordplay, partner)
        for key in sorted(wordplay.get('phrases', {}), key=len, reverse=True):
            prefix = re.match(re.escape(key) + r'[.!]\s+(.+)', text, re.I)
            if prefix:
                text = prefix[1]
                break
        # Understand the same expressive grammar that the speaker can produce.
        text = re.sub(r'^(what|where|when|why|how|who) the \w+ ', r'\1 ', text, flags=re.I)
        interjection = re.match(r'^([\w-]+)[.!]\s+(.+)', text)
        if interjection and interjection[1].lower() in wordplay['words']:
            text = interjection[2]
        low = text.lower()
        memory['turn'] += 1
        reply = None
        feeling_directive_handled = False
        facts = memory['facts']
        definitions = memory.setdefault('definitions', {})
        # The compact representation drives memory and response selection for
        # multi-clause input. Retain unknown clauses in the interpretation.
        assertions = [frame for frame in interpretation['frames'] if frame['act'] == 'assertion']
        if len(interpretation['frames']) + len(interpretation['unparsed']) > 1 and assertions:
            for frame in assertions:
                fact = {key: value for key, value in frame.items() if key not in ('act', 'clause', 'evidence')}
                facts[:] = [old for old in facts if not (old['subject'] == fact['subject'] and old['verb'] == fact['verb'])]
                facts.append(fact)
                memory['topic'] = fact['object']
                if fact['verb'] != 'feel':
                    memory['referent'] = fact['object']
            del facts[:-24]
            reply = self._question_about(facts[-1], str(partner), memory['turn'])
        explain_location = re.fullmatch(r'why (?:are you|did you (?:come|go|wander)) (?:in|to|into) (.+)', text, re.I)
        if explain_location:
            reply = self._location_reason(explain_location[1])
        if low in ('why', 'why is that') and reply is None:
            previous = memory.get('last_subject', {})
            if previous.get('kind') == 'location':
                reply = self._location_reason(previous.get('value'))
            elif previous.get('kind') == 'feeling':
                if getattr(self.lonk, 'trauma', 0) > 5:
                    reply = self._sentence('I have been hurt')
                elif getattr(self.lonk, 'learning_signal', 0) > 0.1:
                    reply = self._sentence('I have been learning new words')
                else:
                    reply = self._sentence('I do not know what caused that feeling')
        # Only imperative speech requests a mood change. Statements of desire
        # and questions containing "feel" must not become contagious commands.
        directive = re.fullmatch(r"(?:please\s+)?(?:(?:don't|do not) do that[, ]+)?feel\s+(.+)", text, re.I)
        if reply is None and directive:
            desired = [word for word in re.findall(r'\b\w+\b', directive[1].lower())
                       if word in self.EMOTION_WORDS or word in ('love', 'peace')]
            if desired:
                memory['desired_feeling'] = list(dict.fromkeys(desired))
                reply = self._sentence('I want to feel ' + ' and '.join(memory['desired_feeling']))
                feeling_directive_handled = True

        place_question = re.fullmatch(r'(?:what do you think about|how do you feel about) (.+)', text, re.I)
        if reply is None and place_question:
            reply = self._place_response(place_question[1], memory)
        location = re.fullmatch(r'I am in (.+)', text, re.I)
        if reply is None and location:
            memory['location'] = location[1]
            memory.setdefault('recent_contributions', []).append('location')
            reply = self._contribution(memory)
        need_question = re.fullmatch(r'why do you need (.+)', low)
        if reply is None and need_question:
            if getattr(self.lonk, 'trauma', 0) > 5 or getattr(self.lonk, 'health', 100) < 40:
                reply = self._sentence('I have been hurt')
            else:
                reply = self._state()
        request = re.fullmatch(r'I need (comfort|reassurance|company|healing|stability)', text, re.I)
        if reply is None and request:
            helper = 'look for help' if request[1].lower() == 'healing' else 'stay'
            reply = self._sentence('I can ' + helper + ' with you')
        if reply is None and re.fullmatch(r'(?:okay|ok|alright|thanks|thank you|got it|sure)(?:[, ]+\w+){0,3}', low):
            reply = self._sentence('okay, ' + str(partner))

        # Questions about the listener are answered from actual simulation state.
        mood_question = bool(re.search(r'\b(?:how are you|how do you feel|how are you feeling|are you (?:okay|ok))\b', low))
        if reply is not None:
            pass
        elif mood_question:
            reply = self._state()
        elif low in ('who are you', 'what is your name'):
            reply = self._sentence('I am ' + getattr(self.lonk, 'name', 'Lonk'))
        elif low == 'where are you':
            place = getattr(self.lonk, 'territory', None)
            reply = self._sentence('I am in ' + place) if place else self._sentence('I do not know the name of this place')
        elif re.fullmatch(r'(hi|hello|hey|greetings)(?:\s+\w+)?', low):
            reply = self._sentence('hello, ' + str(partner)) + ' ' + self._state()
        elif low in ('what about you', 'and you', 'how about you'):
            reply = self._state() if not facts or facts[-1]['verb'] == 'feel' else self._sentence('I have not decided how I feel about ' + facts[-1]['object'])

        # Retrieve remembered assertions, including explicit negation.
        if reply is None:
            question = re.fullmatch(r'what (?:did|do) i (\w+)', low)
            if question and question[1] in self.VERBS:
                relevant = next((f for f in reversed(facts) if f['subject'] == partner and f['verb'] == question[1]), None)
                reply = self._clause(relevant, partner) if relevant else self._sentence('you have not told me what you ' + question[1])
                if relevant:
                    memory['topic'] = memory['referent'] = relevant['object']
            elif low in ('what color is it', 'what colour is it'):
                color = next((w for w in memory.get('referent', memory['topic']).split() if w.lower() in self.COLORS), None)
                reply = self._sentence('it is ' + color) if color else self._sentence('you have not told me its color')
            else:
                preference = re.fullmatch(r'do you (like|love|hate|want|need) (.+)', low)
                if preference:
                    obj = self._view(preference[2], str(partner))
                    if obj in ('it', 'that', 'this'):
                        obj = memory.get('referent') or obj
                    reply = self._sentence('I have not decided whether I ' + preference[1] + ' ' + obj)
        cause = re.fullmatch(r'what made you feel (.+)', low)
        if reply is None and cause:
            reply = self._sentence('I do not know what made me feel ' + cause[1])
        definition_question = re.fullmatch(r'what (?:is (.+)|does (.+) mean)', low)
        if reply is None and definition_question:
            word = definition_question[1] or definition_question[2]
            if word in definitions:
                reply = self._sentence(word + ' is ' + definitions[word])
            else:
                reply = self._sentence('how would you describe ' + word, True)
        definition = re.fullmatch(r'((?:(?:a|an|the) )?[\w-]+) is (.+)', text, re.I)
        if reply is None and definition and definition[1].lower() not in ('it', 'this', 'that', 'he', 'she'):
            word, meaning = definition[1].lower(), self._view(definition[2], str(partner))
            definitions[word] = meaning
            if len(definitions) > 40:
                del definitions[next(iter(definitions))]
            memory['topic'] = memory['referent'] = word
            reply = self._sentence('what makes ' + word + ' ' + meaning, True)

        detail_question = re.fullmatch(r'(where|when|why) (?:did|do) i (\w+)(?: (.+))?', low)
        if reply is None and detail_question and detail_question[2] in self.VERBS:
            relevant = next((f for f in reversed(facts) if f['subject'] == partner and f['verb'] == detail_question[2]), None)
            key = {'where': 'place', 'when': 'time', 'why': 'reason'}[detail_question[1]]
            if relevant and relevant.get(key):
                reply = self._clause(relevant, partner)
                if key == 'reason':
                    reply = reply.rstrip('.') + ' because ' + relevant['reason'] + '.'
            else:
                reply = self._sentence('you have not told me ' + detail_question[1])

        # Update a referent without changing the subject to a random learned word.
        correction = re.fullmatch(r'(?:no[, ]+)?(?:it is|it was) (\w+)', low)
        referent = memory.get('referent') or memory['topic']
        if reply is None and correction and correction[1] in self.COLORS and referent:
            words = [w for w in referent.split() if w.lower() not in self.COLORS]
            if words and words[0].lower() in ('a', 'an', 'the'):
                words.pop(0)
            old_topic = referent
            memory['topic'] = 'the ' + correction[1] + ' ' + ' '.join(words)
            memory['referent'] = memory['topic']
            for fact in facts:
                if fact['object'] == old_topic:
                    fact['object'] = memory['topic']
            reply = self._sentence('you mean ' + memory['topic'], True)

        # Short answers fill the question's missing semantic role. They are not
        # discarded just because the player omitted a subject and verb.
        pending = memory.get('pending')
        if reply is None and pending and facts and '?' not in str(message):
            fact = facts[-1]
            if pending == 'where' and re.match(r'^(?:by|in|near|under|at|beside|behind|on)\b', low):
                fact['place'] = self._view(text, str(partner))
                reply = self._clause(fact, str(partner))
            elif pending == 'when' and re.match(r'^(?:yesterday|today|last|this|at|before|after)\b', low):
                fact['time'] = text
                reply = self._clause(fact, str(partner))
            elif low.startswith('because '):
                fact['reason'] = self._view(text[8:], str(partner))
                reply = self._clause(fact, str(partner)).rstrip('.') + ' because ' + fact['reason'] + '.'

        fact = self._parse(text, str(partner), memory) if reply is None else None
        if fact:
            # A correction to the same assertion replaces it, rather than leaving
            # contradictory facts to be chosen randomly later.
            facts[:] = [f for f in facts if not (f['subject'] == fact['subject'] and f['verb'] == fact['verb'])]
            facts.append(fact)
            del facts[:-24]
            memory['topic'] = fact['object']
            if fact['verb'] != 'feel':
                memory['referent'] = fact['object']
            if fact.get('modal') and fact['subject'] == getattr(self.lonk, 'name', None):
                reply = self._sentence('I ' + fact['modal'] + (' not ' if fact['negative'] else ' ') + fact['verb'] + ' ' + fact['object'])
            elif fact['verb'] == 'feel' and re.search(r'\balso\b', low):
                previous = memory.get('last_subject', {})
                if previous.get('kind') == 'feeling' and previous.get('value') == fact['object']:
                    reply = self._sentence('we both feel ' + fact['object'])
                else:
                    reply = self._question_about(fact, str(partner), memory['turn'])
            else:
                reply = self._question_about(fact, str(partner), memory['turn'])

        # Feelings are adjective complements, not objects of random verbs.
        feeling = re.fullmatch(r'I am (sad|happy|scared|angry|lonely|tired|nervous|hungry)', text, re.I)
        if reply is None and feeling:
            adjective = feeling[1].lower()
            memory['topic'] = adjective
            reply = self._sentence('what made you feel ' + adjective, True)

        if reply is None and low in ('why', 'why is that', 'what do you mean'):
            # Do not invent a reason for the other speaker's actions.
            if facts and memory['last_reply'].endswith('?'):
                reply = self._sentence('I want to understand ' + facts[-1]['object'])
            else:
                reply = self._sentence('which part should I explain', True)
        if reply is None and text:
            focus = memory['topic']
            if low in ('yes', 'no', 'maybe') and focus:
                reply = self._sentence('what changed with ' + focus, True)
            else:
                # Unfamiliar input is material to play with, not an error. Do not
                # store a guessed meaning or turn a guess into a factual claim.
                heard = [w for w in re.findall(r'\b[^\W\d_]{2,24}\b', low)
                         if w in wordplay['words']]
                if len(text.split()) <= 2 and heard:
                    reply = self._experiment(heard[-1], wordplay)
                elif heard:
                    phrase = self._learn_phrase(text, wordplay) if self._external_speaker(partner) else None
                    if phrase:
                        reply = phrase.rstrip('.!?') + '! ' + self._state()
                    else:
                        reply = self._contribution(memory)
                else:
                    reply = self._contribution(memory)

        if reply is None:
            # Autonomous speech is grounded in lived state and existing interests.
            if facts and memory['last_reply'] != self._question_about(facts[-1], str(partner), memory['turn']):
                reply = self._question_about(facts[-1], str(partner), memory['turn'])
            else:
                candidates = [self._state()]
                brain = getattr(self.lonk, 'brain', None)
                if brain is not None:
                    need = brain.get_need(self.lonk)
                    nouns = {'comfort': 'comfort', 'reassurance': 'reassurance',
                             'company': 'company', 'knowledge': 'something new to learn',
                             'healing': 'healing', 'stability': 'stability',
                             'items': 'something to keep', 'territory': 'a place to stay'}
                    if need in nouns:
                        candidates.append(self._sentence('I need ' + nouns[need]))
                candidates.append(self._contribution(memory))
                items = getattr(self.lonk, 'items', [])
                if items:
                    item = random.choice(items)
                    name = item.get('name', 'this') if isinstance(item, dict) else str(item)
                    candidates.append(self._sentence('what would you do with ' + name, True))
                options = [c for c in candidates if c != memory['last_reply']] or candidates
                reply = random.choice(options)

        # Track semantic lines across partners, before expressive decoration.
        # Changing rooms or listeners must not reset the repetition budget.
        retrieval = bool(re.match(r'^(?:what (?:did|do) i\b|(?:where|when|why) (?:did|do) i\b|what colou?r\b|what (?:is|does)\b|who are you\b|where are you\b)', low))
        contextual = bool(explain_location or low in ('why', 'why is that') or feeling_directive_handled)
        recent_lines = wordplay.setdefault('recent_social_lines', [])
        if not self._external_speaker(partner):
            blocked = set(recent_lines[-6:]) | {self._sentence(text).casefold()}
            if not retrieval and not correction and not contextual and reply.casefold() in blocked:
                reply = self._contribution(memory, avoid=blocked)
            recent_lines.append(reply.casefold())
            del recent_lines[:-8]

        # Learned vocabulary colors every kind of conversational construction,
        # not just mood reports. Keep explicit fact retrieval and corrections exact.
        if not retrieval and not correction and not contextual and 'cannot follow that sentence' not in reply:
            reply = self._wordplay(reply, wordplay)
        semantic_reply = reply.rsplit('! ', 1)[-1]
        subject = re.match(r'I am in (.+?)(?:\.|$)', semantic_reply)
        feeling_subject = re.fullmatch(r'I feel (.+)\.', semantic_reply)
        if subject:
            memory['last_subject'] = {'kind': 'location', 'value': subject[1]}
        elif feeling_subject:
            memory['last_subject'] = {'kind': 'feeling', 'value': feeling_subject[1]}
        else:
            memory['last_subject'] = {'kind': 'statement', 'value': reply}
        if not retrieval and not correction:
            reply = express_emojis(reply, wordplay, include_mood=raw_input is None)
        memory['last_reply'] = reply
        memory['pending'] = reply.split()[0].lower() if reply.endswith('?') else None
        world = getattr(self.lonk, 'world', None)
        trace = getattr(world, 'semantic_trace', self.trace)
        sequence = trace.append(getattr(self.lonk, 'semantic_id', getattr(self.lonk, 'name', 'Lonk')),
                               str(partner), getattr(world, 'tick', 0), raw_input,
                               interpretation, reply, before, memory)
        if self.lonk is not None:
            self.lonk.last_spoken = reply
            self.lonk.semantic_summary = {**interpretation, 'trace_sequence': sequence}
        return reply
