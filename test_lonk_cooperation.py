import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_lonk_dialogue as dialogue_tests


class CooperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dialogue_tests.IntegrationTests.setUpClass()
        cls.sim = dialogue_tests.IntegrationTests.sim

    def pair(self):
        first = self.sim.Lonk(name='Glink', _loading=True)
        second = self.sim.Lonk(name='Plump', _loading=True)
        world = SimpleNamespace(tick=0, lonks=[first, second], social_chance=0.5,
                                catchphrase_chance=0.05, narrate=print)
        first.world = second.world = world
        return first, second, world

    def test_help_repairs_damage_and_builds_mutual_relationships(self):
        first, second, _ = self.pair()
        second.health, second.trauma = 50, 20
        with contextlib.redirect_stdout(io.StringIO()):
            outcome = first.execute_action({'verb': 'help', 'target_type': 'other'})
        self.assertTrue(outcome['success'])
        self.assertEqual(second.health, 54)
        self.assertLess(second.trauma, 20)
        self.assertGreater(first.relationships[second.name], 0)
        self.assertGreater(second.relationships[first.name], 0)

    def test_material_gifts_are_supplies_that_can_be_shared(self):
        first, second, _ = self.pair()
        first.receive_gift('big bag of seed')
        self.assertNotIn('big bag of seed', first.emotion)
        self.assertEqual(first.items[0]['name'], 'big bag of seed')
        self.assertEqual(first.choose_cooperative_action(), 'give')
        with contextlib.redirect_stdout(io.StringIO()):
            first.execute_action({'verb': 'give', 'target_type': 'other'})
        self.assertFalse(first.items)
        self.assertEqual(second.items[0]['name'], 'big bag of seed')

    def test_exploration_really_collects_items(self):
        first, _, _ = self.pair()
        with contextlib.redirect_stdout(io.StringIO()), patch.dict(self.sim.TOGGLES, shinywars=True), patch.object(self.sim.random, 'random', return_value=0):
            first.execute_action({'verb': 'explore', 'target_type': 'other'})
        self.assertTrue(first.items)
        self.assertIn(first.territory.lower(), first.vocabulary)

    def test_teacher_selects_something_the_student_does_not_know(self):
        first, second, _ = self.pair()
        first.vocabulary = {'moss': 1, 'floob': 1}
        second.vocabulary = {'moss': 1}
        with contextlib.redirect_stdout(io.StringIO()):
            result = first._verb_teach(second, 'moss', None)
        self.assertTrue(result['success'])
        self.assertIn('floob', second.vocabulary)

    def test_fighting_is_rate_limited_but_still_possible(self):
        first, second, world = self.pair()
        first.rival = second
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=1):
            first.duel()
            health = second.health
            first.duel()
            self.assertEqual(second.health, health)
            world.tick = 3
            first.duel()
        self.assertLess(second.health, health)

    def test_unprovoked_attack_policy_usually_selects_cooperative_alternative(self):
        first, second, _ = self.pair()
        second.health = 50
        with patch.object(first.brain, 'choose_action', return_value=3), patch.object(first.brain, 'get_need', return_value='idle'), patch.object(self.sim.random, 'random', return_value=0.99):
            self.assertEqual(first.choose_action(), 'help')

    def test_action_learning_credits_exploration_instead_of_idle(self):
        first, _, _ = self.pair()
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=0.99), patch.object(first.brain, 'record') as record:
            first.act('explore')
        self.assertEqual(record.call_args.args[1], first.ACTIONS.index('explore'))

    def test_physical_gifts_survive_saving_and_loading(self):
        first, _, _ = self.pair()
        first.receive_gift('soggy sock')
        saved = first.to_dict()
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(saved)
        self.assertEqual(restored.items, first.items)
        self.assertEqual(restored.inventory, ['soggy sock'])
        saved.pop('item_details')
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(saved)
        self.assertEqual(restored.items[0]['name'], 'soggy sock')

    def test_disabling_violence_also_disables_bonks(self):
        first, second, _ = self.pair()
        with patch.dict(self.sim.TOGGLES, violence=False):
            result = first._verb_bonk(second, None, None)
        self.assertFalse(result['success'])
        self.assertEqual(second.trauma, 0)


if __name__ == '__main__':
    unittest.main()
