"""Offline semantic records: preserve input, project recognized structure separately.

The trace replays dialogue-memory changes, not the complete simulated world.
Hashes detect broken chains; they are not signatures or proof against a rewritten file.
"""
import copy
import hashlib
import json
import re
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def compress(text, speaker, listener, clean, parse, memory):
    """Extract supported distinctions; never turn unrecognized language into a guess."""
    frames, unknown = [], []
    working = copy.deepcopy(memory)
    for index, match in enumerate(re.finditer(r'[^.!?\n]+[.!?]?', str(text))):
        original = match.group().strip()
        clause = clean(original)
        if not clause:
            continue
        fact = parse(clause, speaker, working)
        if fact:
            frames.append({'clause': index, 'act': 'assertion', 'evidence': 'grammar_rule', **fact})
            working['topic'] = fact['object']
            if fact['verb'] != 'feel':
                working['referent'] = fact['object']
            continue
        question = re.fullmatch(r'what (did|do) i (\w+)', clause, re.I)
        if question:
            frames.append({'clause': index, 'act': 'question', 'subject': speaker,
                           'verb': question[2].lower(), 'slot': 'object', 'evidence': 'grammar_rule'})
            continue
        state = re.fullmatch(r'I am (not )?(.+)', clause, re.I)
        if state:
            frames.append({'clause': index, 'act': 'state_report', 'subject': speaker,
                           'verb': 'be', 'object': state[2], 'negative': bool(state[1]),
                           'evidence': 'grammar_rule'})
            continue
        unknown.append({'clause': index, 'text': original})
    return {'version': 1, 'speaker': speaker, 'listener': listener, 'frames': frames,
            'unparsed': unknown, 'coverage': 'complete' if frames and not unknown else 'partial' if frames else 'unparsed'}


class SemanticTrace:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.records = []
        self.projections = {}
        self.tail = '0' * 64
        if self.path and self.path.exists():
            previous = self.tail
            with self.path.open(encoding='utf-8') as stream:
                for number, line in enumerate(stream, 1):
                    record = json.loads(line)
                    self.verify(record, previous)
                    if record['sequence'] != number:
                        raise ValueError('Semantic trace sequence mismatch')
                    self._apply(self.projections, record)
                    previous = record['hash']
            self.tail = previous
            self.sequence = number if previous != '0' * 64 else 0
        else:
            self.sequence = 0

    @staticmethod
    def verify(record, previous):
        body = {key: value for key, value in record.items() if key != 'hash'}
        if record['previous_hash'] != previous or hashlib.sha256(canonical(body).encode('utf-8')).hexdigest() != record['hash']:
            raise ValueError('Semantic trace hash mismatch')

    def append(self, agent, speaker, tick, raw, interpretation, reply, before, after):
        updates = {key: copy.deepcopy(value) for key, value in after.items() if key not in before or before[key] != value}
        removed = [key for key in before if key not in after]
        key = (agent, speaker)
        baseline = copy.deepcopy(before) if self.projections.get(key) != before else None
        body = {'version': 1, 'sequence': self.sequence + 1, 'previous_hash': self.tail,
                'agent': agent, 'speaker': speaker, 'tick': tick, 'raw_input': raw,
                'interpretation': copy.deepcopy(interpretation), 'reply': reply,
                'baseline': baseline, 'updates': updates, 'removed': removed}
        record = {**body, 'hash': hashlib.sha256(canonical(body).encode('utf-8')).hexdigest()}
        if self.path:
            # One simulation thread owns this trace. Do not swallow write errors.
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(canonical(record) + '\n')
                stream.flush()
        else:
            self.records.append(record)
        self.sequence += 1
        self.tail = record['hash']
        self._apply(self.projections, record)
        return record['sequence']

    @staticmethod
    def _apply(states, record):
        key = (record['agent'], record['speaker'])
        if record['baseline'] is not None:
            state = copy.deepcopy(record['baseline'])
        elif key in states:
            state = copy.deepcopy(states[key])
        else:
            raise ValueError('Missing dialogue projection baseline')
        state.update(copy.deepcopy(record['updates']))
        for field in record['removed']:
            state.pop(field, None)
        states[key] = state

    @classmethod
    def replay(cls, records):
        """Recover each agent/partner's recorded dialogue-memory projection.

        Baselines explicitly support loading an earlier save: the history stays
        appended while the projection can branch back to that saved context.
        """
        states, previous = {}, '0' * 64
        for number, record in enumerate(records, 1):
            cls.verify(record, previous)
            if record['sequence'] != number:
                raise ValueError('Semantic trace sequence mismatch')
            cls._apply(states, record)
            previous = record['hash']
        return states


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verify a dialogue trace and reconstruct its memory projections.')
    parser.add_argument('trace', type=Path)
    args = parser.parse_args()
    with args.trace.open(encoding='utf-8') as stream:
        records = [json.loads(line) for line in stream]
    states = SemanticTrace.replay(records)
    print(f'Valid hash chain: {len(records)} events; reconstructed {len(states)} dialogue contexts.')
