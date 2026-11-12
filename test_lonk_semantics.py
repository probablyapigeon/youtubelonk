import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from lonk_semantics import SemanticTrace, compress
from lonk_dialogue import DialogueGenerator
import test_lonk_dialogue as dialogue_tests


class CompressionTests(unittest.TestCase):
    def setUp(self):
        self.lonk = dialogue_tests.character()
        self.engine = DialogueGenerator(self.lonk)

    def test_compound_input_preserves_distinct_facts_and_negation(self):
        raw = 'I found a blue rock. I do not like moss.'
        self.engine.generate_response(raw, target='Player')
        self.assertEqual(self.engine.generate_response('what did I find?', target='Player'), 'You found a blue rock.')
        self.assertEqual(self.engine.generate_response('what do I like?', target='Player'), 'You do not like moss.')
        record = self.engine.trace.records[0]
        self.assertEqual(record['raw_input'], raw)
        frames = record['interpretation']['frames']
        self.assertEqual(len(frames), 2)
        self.assertTrue(frames[1]['negative'])

    def test_pronouns_follow_previous_clauses_inside_the_projection(self):
        summary = compress('I found a blue rock. I lost it.', 'Player', 'Sharp',
                           self.engine._clean, self.engine._parse, self.engine._memory('Player'))
        self.assertEqual(summary['frames'][1]['object'], 'a blue rock')

    def test_unknown_language_is_preserved_without_guessed_meaning(self):
        raw = 'I found a blue rock. Wubba Lubba Dub Dub!'
        self.engine.generate_response(raw, target='Player')
        record = self.engine.trace.records[0]
        self.assertEqual(record['raw_input'], raw)
        self.assertEqual(record['interpretation']['coverage'], 'partial')
        self.assertIn('Wubba Lubba Dub Dub', record['interpretation']['unparsed'][0]['text'])

    def test_replay_reconstructs_actual_dialogue_memory(self):
        for text in ('I found a blue rock. I like moss.', 'what did I find?', 'no it was red', None):
            self.engine.generate_response(text, target='Player')
        states = SemanticTrace.replay(self.engine.trace.records)
        self.assertEqual(states[('Sharp', 'Player')], self.lonk.dialogue_state['Player'])
        self.assertIsNotNone(self.engine.trace.records[0]['baseline'])
        self.assertIsNone(self.engine.trace.records[1]['baseline'])

    def test_changed_history_and_deleted_events_are_detected(self):
        self.engine.generate_response('I found a blue rock', target='Player')
        self.engine.generate_response('what did I find?', target='Player')
        changed = copy.deepcopy(self.engine.trace.records)
        changed[0]['raw_input'] = 'I found a red rock'
        with self.assertRaises(ValueError):
            SemanticTrace.replay(changed)
        with self.assertRaises(ValueError):
            SemanticTrace.replay(self.engine.trace.records[1:])

    def test_file_trace_can_resume_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.jsonl'
            self.engine.trace = SemanticTrace(path)
            self.engine.generate_response('I found a blue rock', target='Player')
            self.engine.trace = SemanticTrace(path)
            self.engine.generate_response('what did I find?', target='Player')
            records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records), 2)
            states = SemanticTrace.replay(records)
            self.assertEqual(states[('Sharp', 'Player')], self.lonk.dialogue_state['Player'])

    def test_record_keeps_unicode_and_line_breaks_verbatim(self):
        raw = 'Wubba!\nI found a \u2603-shaped rock.'
        self.engine.generate_response(raw, target='Player')
        self.assertEqual(self.engine.trace.records[0]['raw_input'], raw)

    def test_interpretations_do_not_confuse_can_with_did(self):
        self.engine.generate_response('you can want moss. I found a rock.', target='Player')
        frame = self.engine.trace.records[0]['interpretation']['frames'][0]
        self.assertEqual(frame['modal'], 'can')

    def test_real_lonk_uses_world_trace_and_preserves_identity_across_save(self):
        dialogue_tests.IntegrationTests.setUpClass()
        sim = dialogue_tests.IntegrationTests.sim
        lonk = sim.Lonk(name='Sharp', _loading=True)
        world = SimpleNamespace(tick=3, lonks=[lonk], semantic_trace=SemanticTrace(), config={})
        lonk.world = world
        lonk.respond_to_player('I found a blue rock. I lost a spoon.')
        self.assertEqual(len(world.semantic_trace.records), 1)
        self.assertEqual(world.semantic_trace.records[0]['agent'], lonk.semantic_id)
        with contextlib.redirect_stdout(io.StringIO()):
            restored = sim.Lonk.from_dict(lonk.to_dict(), world=world)
        self.assertEqual(restored.semantic_id, lonk.semantic_id)
        self.assertEqual(restored.semantic_summary, lonk.semantic_summary)


if __name__ == '__main__':
    unittest.main()
