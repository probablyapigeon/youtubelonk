import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lonk_visuals import (body_for, learn_emojis, express_emojis, display_width,
                          wrap_display, ColorOutput, event_color, RESET, enable_colors,
                          EMOJI_ALPHABET)
from lonk_dialogue import DialogueGenerator


class VisualTests(unittest.TestCase):
    def test_identity_body_survives_movement_and_reloading(self):
        lonk = SimpleNamespace(name='Grorp', semantic_id='stable-identity', territory='Pit')
        body = body_for(lonk)
        lonk.territory = 'City'
        self.assertEqual(body_for(lonk), body)
        self.assertEqual(body_for(SimpleNamespace(name='Renamed', semantic_id='stable-identity')), body)

    def test_learns_joined_flags_keycaps_and_skin_tones_whole(self):
        state = {}
        emojis = ['🧑🏽‍🚀', '🇺🇸', '1️⃣', '❤️', '🪼', '🏳️‍🌈']
        learn_emojis('hello ' + ' '.join(emojis), state)
        self.assertEqual(set(state['emojis']), set(emojis))
        self.assertTrue(express_emojis('Hello.', state).endswith('🏳️‍🌈'))

    def test_learned_emoji_is_used_and_spreads_between_lonks(self):
        first = DialogueGenerator(SimpleNamespace(name='Grorp'))
        second = DialogueGenerator(SimpleNamespace(name='Krip'))
        reply = first.generate_response('🧑🏽‍🚀', target='Player')
        self.assertIn('🧑🏽‍🚀', reply)
        response = second.generate_response(reply, target='Grorp')
        self.assertIn('🧑🏽‍🚀', response)
        self.assertIn('🧑🏽‍🚀', second.lonk.wordplay_state['emojis'])

    def test_spontaneous_expression_can_explore_beyond_mood_palette(self):
        self.assertGreater(len(EMOJI_ALPHABET), 1000)
        with patch('lonk_visuals.random.random', return_value=0), patch('lonk_visuals.random.choice', return_value='🪼'):
            self.assertEqual(express_emojis('I have moss.', {}, include_mood=True), 'I have moss. 🪼')

    def test_emoji_columns_wrap_and_align(self):
        self.assertEqual(display_width('🐸 Grorp'), 8)
        self.assertEqual(display_width('🧑🏽‍🚀'), 2)
        self.assertEqual(display_width('🇺🇸'), 2)
        rows = wrap_display('🐸 Grorp 🐱 Krip 🧑🏽‍🚀 traveler', 15)
        self.assertTrue(all(display_width(row) <= 15 for row in rows))
        self.assertEqual(' '.join(rows), '🐸 Grorp 🐱 Krip 🧑🏽‍🚀 traveler')

    def test_colors_follow_individual_events_and_strip_cleanly(self):
        output = io.StringIO()
        colored = ColorOutput(output)
        colored.write('Grorp BONKS Krip!\nGrorp gives moss to Krip!\n')
        result = output.getvalue()
        self.assertIn('\x1b[91mGrorp BONKS Krip!', result)
        self.assertIn('\x1b[93mGrorp gives moss to Krip!', result)
        self.assertTrue(result.endswith(RESET))
        self.assertIs(enable_colors(output), output)

    def test_paced_narration_color_does_not_enter_speech(self):
        import test_tts_regression as speech_tests
        world = speech_tests.SpeechTests().world()
        world.tts_enabled = True
        world.tts_engine = object()
        spoken = []
        def speak(name, line, completed=None, **kwargs):
            spoken.append(line)
            completed.set()
        world.speak = speak
        raw = io.StringIO()
        with contextlib.redirect_stdout(ColorOutput(raw)), patch.object(speech_tests.mod.time, 'sleep'):
            world.narrate('Grorp BONKS Krip!')
        self.assertEqual(spoken, ['Grorp BONKS Krip!'])
        self.assertEqual(raw.getvalue(), event_color(spoken[0]) + spoken[0] + '\n' + RESET)


if __name__ == '__main__':
    unittest.main()
