"""Mood changes must follow learning and treatment, not a shared downward loop."""
import contextlib
import io
import unittest
from unittest.mock import patch
import test_lonk_dialogue as dialogue_tests


class EmotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dialogue_tests.IntegrationTests.setUpClass()
        cls.sim = dialogue_tests.IntegrationTests.sim

    def lonk(self, name='Probe'):
        return self.sim.Lonk(name=name, _loading=True)

    def test_quiet_life_does_not_drain_all_courage_and_joy(self):
        lonk = self.lonk()
        for _ in range(100):
            lonk.emotional_update()
        self.assertGreater(lonk.emotion['joy'], 30)
        self.assertGreater(lonk.emotion['courage'], 30)
        self.assertGreater(lonk.state[2], 0.15)

    def test_new_learning_raises_arousal_without_inventing_trauma(self):
        lonk = self.lonk()
        before = lonk.state[2]
        lonk.remember_player_words('floob glimmerwidget')
        self.assertGreater(lonk.state[2], before)
        after = lonk.state[2]
        lonk.remember_player_words('floob glimmerwidget')
        self.assertEqual(lonk.state[2], after)
        self.assertEqual(lonk.trauma, 0)

    def test_bonk_creates_trauma_and_lowers_valence(self):
        victim, attacker = self.lonk(), self.lonk('Brob')
        before = victim.state[3]
        with contextlib.redirect_stdout(io.StringIO()):
            attacker._verb_bonk(victim, None, None)
        self.assertGreater(victim.trauma, 0)
        self.assertLess(victim.state[3], before)

    def test_duel_creates_trauma_as_well_as_health_damage(self):
        victim, attacker = self.lonk(), self.lonk('Brob')
        attacker.rival = victim
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=1):
            attacker.duel()
        self.assertLess(victim.health, self.sim.MAX_HEALTH)
        self.assertGreater(victim.trauma, 0)

    def test_own_success_and_failure_change_valence_in_opposite_directions(self):
        success, failure = self.lonk(), self.lonk()
        action = {'verb': 'learn', 'target_type': 'self'}
        success._record_action_outcome(action, {'reward': 0.4})
        failure._record_action_outcome(action, {'reward': -0.4})
        self.assertGreater(success.state[3], failure.state[3])

    def test_supportive_player_conversation_has_strong_immediate_effect(self):
        lonk = self.lonk()
        lonk.emotion['anxiety'] = 80
        before = lonk.state[3]
        with contextlib.redirect_stdout(io.StringIO()):
            lonk.hear('Player', 'I love you and you are safe', is_player=True)
        self.assertGreater(lonk.state[3], before + 0.1)
        self.assertGreater(lonk.emotion['joy'], 55)
        self.assertLess(lonk.emotion['anxiety'], 80)

    def test_insults_hurt_but_teaching_a_swear_is_not_an_insult(self):
        insulted, taught = self.lonk(), self.lonk()
        with contextlib.redirect_stdout(io.StringIO()):
            insulted.hear('Player', 'you are stupid and worthless', is_player=True)
            taught.hear('Player', 'fuck', is_player=True)
        self.assertLess(insulted.state[3], taught.state[3])
        self.assertEqual(taught.trauma, 0)

    def test_gifts_act_on_real_health_and_underlying_mood(self):
        lonk = self.lonk()
        lonk.health = 20
        before = lonk.state[3]
        lonk.receive_gift('health')
        self.assertEqual(lonk.health, 45)
        self.assertNotIn('health', lonk.emotion)
        self.assertGreater(lonk.state[3], before)

    def test_comfort_can_reduce_bonk_trauma(self):
        lonk = self.lonk()
        lonk.trauma = 30
        lonk.emotion['anxiety'] = 80
        lonk.receive_gift('comfort')
        self.assertLess(lonk.trauma, 30)
        self.assertLess(lonk.emotion['anxiety'], 80)

    def test_gift_effect_persists_beyond_the_next_tick(self):
        gifted, control = self.lonk(), self.lonk()
        gifted.receive_gift('joy')
        for _ in range(10):
            gifted.emotional_update()
            control.emotional_update()
        self.assertGreater(gifted.state[3], control.state[3] + 0.05)
        self.assertGreater(gifted.emotion['joy'], control.emotion['joy'] + 5)

    def test_peer_conversation_teaches_and_changes_the_listeners_mood(self):
        lonk = self.lonk()
        conversation = self.sim.Conversation('Brob', lonk.name)
        before = lonk.state[2:4]
        with contextlib.redirect_stdout(io.StringIO()):
            lonk.respond_in_conversation(conversation, 'I found a glimmerwidget', 1)
        self.assertIn('glimmerwidget', lonk.knowledge)
        self.assertGreater(lonk.state[2], before[0])
        self.assertGreater(lonk.state[3], before[1])

    def test_insult_action_has_an_effect_even_with_playful_wording(self):
        victim, attacker = self.lonk(), self.lonk('Brob')
        before = victim.state[3]
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'choice', return_value='You smell like moss!'):
            attacker._verb_insult(victim, None, None)
        self.assertLess(victim.state[3], before)

    def test_mood_signals_and_trauma_survive_save_load(self):
        lonk = self.lonk()
        lonk.experience(valence=-0.4, trauma=12, learning=2)
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(lonk.to_dict())
        self.assertEqual(restored.trauma, lonk.trauma)
        self.assertEqual(restored.learning_signal, lonk.learning_signal)
        self.assertEqual(restored.action_valence, lonk.action_valence)
        self.assertEqual(restored.get_xembra_state(), lonk.get_xembra_state())

    def test_player_commands_change_health_and_process_speech_once(self):
        import test_tts_regression as speech_tests
        from unittest.mock import Mock
        world = speech_tests.SpeechTests().world()
        world.auto_mode = False
        world.command_parser = self.sim.CommandParser()
        lonk = self.lonk('Probe')
        lonk.health = 20
        world.lonks = [lonk]
        world.save = Mock()
        with contextlib.redirect_stdout(io.StringIO()), patch('builtins.input', side_effect=[
                '/gift Probe health', '/say Probe I love you and you are safe', 'quit']):
            world.interactive_loop()
        self.assertEqual(lonk.health, 45)
        self.assertEqual(len(lonk.memory['player_interactions']), 1)
        self.assertGreater(lonk.emotion['joy'], 60)


if __name__ == '__main__':
    unittest.main()
