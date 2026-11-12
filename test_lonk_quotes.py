"""Local corpus parsing, real phrase learning, and quote command integration."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lonk_quotes import QuoteLibrary
import test_lonk_live as live_tests


class QuoteFileTests(unittest.TestCase):
    def test_plain_text_bom_comments_and_case_insensitive_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'quotes.txt'
            path.write_text('# comment\n\nQuantum moss dances sideways.\nquantum moss dances sideways.\n🧑🏽‍🚀 Space moss sings!\n', encoding='utf-8-sig')
            library = QuoteLibrary()
            self.assertEqual(library.load_file(path), 2)
            self.assertFalse(library.enabled)
            self.assertIn('🧑🏽‍🚀 Space moss sings!', library.quotes)

    def test_json_and_jsonl_string_and_object_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            for filename, text in (
                ('quotes.json', json.dumps({'quotes': ['Moss one.', {'quote': 'Moss two.'}, {'text': 'Moss three.'}]})),
                ('quotes.jsonl', '\n'.join(json.dumps(row) for row in ['Moss one.', {'quote': 'Moss two.'}, {'text': 'Moss three.'}])),
            ):
                path = Path(folder)/filename
                path.write_text(text, encoding='utf-8')
                library = QuoteLibrary()
                self.assertEqual(library.load_file(path), 3)
                self.assertEqual(library.quotes, ['Moss one.', 'Moss two.', 'Moss three.'])

    def test_invalid_imports_do_not_erase_existing_library(self):
        library = QuoteLibrary()
        library.quotes = ['Original moss.']
        with tempfile.TemporaryDirectory() as folder:
            for filename, text in [('bad.json', '[invalid'), ('wrong.json', '[123]'),
                                   ('empty.txt', '# only comments'), ('long.txt', 'x'*2001)]:
                path = Path(folder)/filename
                path.write_text(text)
                with self.assertRaises(ValueError):
                    library.load_file(path)
                self.assertEqual(library.quotes, ['Original moss.'])
            path = Path(folder)/'many.txt'
            path.write_text('One\nTwo\nThree')
            with patch.object(QuoteLibrary, 'MAX_QUOTES', 2), self.assertRaises(ValueError):
                library.load_file(path)
            with patch.object(QuoteLibrary, 'MAX_FILE_BYTES', 2), self.assertRaises(ValueError):
                library.load_file(path)
            self.assertEqual(library.quotes, ['Original moss.'])

    def test_windows_paths_with_spaces_are_accepted(self):
        library = QuoteLibrary()
        with tempfile.TemporaryDirectory(prefix='My Quotes ') as folder:
            path = Path(folder)/'chosen quotes.txt'
            path.write_text('Quantum moss dances sideways.')
            result = library.command(None, f'load "{path}"')
            self.assertIn('Loaded 1 quotes', result)

    def test_saved_library_round_trip_and_empty_legacy_state(self):
        library = QuoteLibrary()
        library.quotes = ['Moss one.', 'Moss two.']
        library.enabled, library.interval, library.last_tick = True, 15, 420
        library.last_quote['Grub'] = 'Moss two.'
        restored = QuoteLibrary.from_dict(json.loads(json.dumps(library.to_dict())))
        self.assertEqual(restored.to_dict(), library.to_dict())
        self.assertFalse(QuoteLibrary.from_dict(None).enabled)


class QuoteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        live_tests.SpatialIntegrationTests.setUpClass()
        cls.sim = live_tests.SpatialIntegrationTests.sim

    def world(self):
        w, c, screen = live_tests.SpatialIntegrationTests().world()
        w.narrate = Mock()
        w.quote_library = QuoteLibrary()
        w.quote_library.quotes = ['Quantum moss dances sideways.']
        return w, c, screen

    def test_reader_learns_real_phrases_and_neighbors_only_hear_local_reading(self):
        w, c, _ = self.world()
        reader, neighbor, remote = w.lonks
        reader.territory = neighbor.territory = next(iter(c.rooms))
        remote.territory = list(c.rooms)[2]
        neighbor.hear = Mock(wraps=neighbor.hear)
        remote.hear = Mock(wraps=remote.hear)
        before = copy.deepcopy(getattr(reader, 'dialogue_state', {}))
        quote = w.quote_library.teach(w, reader)
        self.assertEqual(quote, 'Quantum moss dances sideways.')
        self.assertIn('quantum moss dances sideways', reader.wordplay_state['phrases'])
        self.assertEqual(reader.memory['events'][-1]['speaker'], 'Quote Archive')
        self.assertFalse(reader.memory['events'][-1]['player'])
        self.assertEqual(getattr(reader, 'dialogue_state', {}), before)
        neighbor.hear.assert_called_once_with(reader, quote)
        remote.hear.assert_not_called()
        w.narrate.assert_called_once_with(f'💬 {reader.name}: {quote}')
        response = reader.dialogue_generator.generate_response(None, target='Player')
        self.assertIn('Quantum moss dances sideways', response)

    def test_teaching_preserves_emoji_and_avoids_consecutive_identical_quotes(self):
        w, _, _ = self.world()
        library = w.quote_library
        library.quotes = ['Space moss glows softly. 🧑🏽‍🚀', 'Purple rocks dance sideways.']
        first = library.teach(w, w.lonks[0])
        second = library.teach(w, w.lonks[0])
        self.assertNotEqual(first, second)
        self.assertIn('🧑🏽‍🚀', w.lonks[0].wordplay_state['emojis'])

    def test_automatic_teaching_waits_for_cadence_and_off_stops_it(self):
        w, _, _ = self.world()
        library = w.quote_library
        library.command(w, 'on 12')
        start = w.tick
        for tick in range(start+1, start+12):
            w.tick = tick
            library.maybe_teach(w)
        w.narrate.assert_not_called()
        w.tick = start+12
        library.maybe_teach(w)
        library.maybe_teach(w)
        self.assertEqual(w.narrate.call_count, 1)
        library.command(w, 'off')
        w.tick += 24
        library.maybe_teach(w)
        self.assertEqual(w.narrate.call_count, 1)

    def test_bad_target_empty_library_and_interval_validation(self):
        w, _, _ = self.world()
        for command in ('teach Missing', 'on 0', 'on -1', 'on 10001', 'on banana'):
            with self.assertRaises(ValueError):
                w.quote_library.command(w, command)
        w.quote_library.command(w, 'clear')
        with self.assertRaises(ValueError):
            w.quote_library.command(w, 'on')

    def test_world_tick_uses_enabled_library(self):
        w, _, _ = self.world()
        w.quote_library.command(w, 'on 1')
        w.starting_population, w.arrival_chance, w.dream_chance = 0, 0, 0
        w.wp_ab_state = {}
        for p in w.lonks:
            p.act, p.choose_action = Mock(), Mock(return_value='idle')
        w.civilization.begin_tick = Mock()
        w.civilization.finish_tick = Mock()
        w.civilization.extra_turns = Mock(return_value=[])
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim, 'EPISTEMOLOGY_ON', False):
            w._advance_world_tick()
        w.narrate.assert_called_once()
        self.assertIn('Quantum moss dances sideways.', w.narrate.call_args.args[0])

    def test_real_save_load_restores_library_and_learned_phrases(self):
        with contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as folder:
            w = self.sim.LonkWorld(num_lonks=2)
            w.quote_library = QuoteLibrary()
            w.quote_library.quotes = ['Quantum moss dances sideways.']
            reader = w.lonks[0]
            w.quote_library.teach(w, reader)
            w.quote_library.command(w, 'on 12')
            path = str(Path(folder)/'world.json')
            w.save(path)
            w.quote_library = QuoteLibrary()
            self.assertTrue(w.load(path))
            self.assertEqual(w.quote_library.quotes, ['Quantum moss dances sideways.'])
            self.assertTrue(w.quote_library.enabled)
            restored = w.get_lonk(reader.name)
            self.assertIn('quantum moss dances sideways', restored.wordplay_state['phrases'])

    def test_interactive_import_teach_and_controls(self):
        w, _, _ = self.world()
        del w.__dict__['narrate']
        w.auto_mode, w.tts_error = False, None
        w.command_parser = self.sim.CommandParser()
        w.save, w._stop_tts_thread = Mock(), Mock()
        console = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='My Quotes ') as folder:
            path = Path(folder)/'quotes.txt'
            path.write_text('Quantum moss dances sideways.')
            commands = iter([f'/quotes load "{path}"', '/quotes teach Flonk', '/quotes on 12', '/quotes off', 'quit'])
            with contextlib.redirect_stdout(console), patch('builtins.input', side_effect=lambda prompt: next(commands)), patch.object(self.sim.time, 'sleep'):
                w.interactive_loop()
        self.assertNotIn('Error:', console.getvalue())
        self.assertNotIn('Quote library:', console.getvalue())
        self.assertFalse(w.quote_library.enabled)
        self.assertTrue(any('Quantum moss dances sideways.' in row for row in w._live_view.feed))
        w.save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
