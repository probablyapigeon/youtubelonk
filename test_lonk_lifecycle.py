import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_lonk_dialogue as dialogue_tests


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dialogue_tests.IntegrationTests.setUpClass()
        cls.sim = dialogue_tests.IntegrationTests.sim

    def creature(self, settings=None):
        world = SimpleNamespace(config={'world': settings or {}}, tick=1, lonks=[], pending_births=[])
        lonk = self.sim.Lonk(name='Brump', world=world, _loading=True)
        world.lonks.append(lonk)
        return lonk, world

    def test_configured_lifespan_is_used(self):
        lonk, _ = self.creature({'lifespan': [120, 120]})
        self.assertEqual(lonk.lifespan, 120)

    def test_healthy_newborn_does_not_randomly_die_even_with_zero_random_draw(self):
        lonk, world = self.creature({'lifespan': [120, 120]})
        with patch.object(self.sim.random, 'random', return_value=0):
            for tick in range(1, 101):
                world.tick = tick
                lonk.age_tick()
        self.assertTrue(lonk.alive)
        self.assertEqual(lonk.age, 100)
        self.assertFalse(world.pending_births)

    def test_annex_extra_action_does_not_double_chronological_age(self):
        lonk, world = self.creature()
        lonk.age_tick(); lonk.age_tick()
        self.assertEqual(lonk.age, 1)
        world.tick += 1
        lonk.age_tick(); lonk.age_tick()
        self.assertEqual(lonk.age, 2)

    def test_old_age_still_has_a_clear_cause(self):
        lonk, world = self.creature({'lifespan': [3, 3]})
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(self.sim.random, 'random', return_value=1):
            for tick in range(1, 4):
                world.tick = tick
                lonk.age_tick()
        self.assertFalse(lonk.alive)
        self.assertEqual(lonk.death_cause, 'old age')
        self.assertIn('old age; age 3/3', output.getvalue())

    def test_optional_random_accidents_are_configurable_and_labelled(self):
        lonk, _ = self.creature({'random_death_chance': 1})
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=1):
            lonk.age_tick()
        # A draw of exactly 1 is outside [0,1) and deliberately does not trigger.
        self.assertTrue(lonk.alive)
        lonk.last_aged_tick = None
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=0.5):
            lonk.age_tick()
        self.assertFalse(lonk.alive)
        self.assertIn('random accident', lonk.death_cause)

    def test_legacy_lifespan_is_extended_without_resetting_age_or_reviving_dead(self):
        lonk, world = self.creature({'lifespan': [90, 180]})
        saved = lonk.to_dict()
        saved.pop('lifecycle_version')
        saved['age'], saved['lifespan'] = 20, 35
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(saved, world)
        self.assertEqual(restored.age, 20)
        self.assertEqual(restored.lifespan, 90)
        saved['alive'] = False
        with contextlib.redirect_stdout(io.StringIO()):
            dead = self.sim.Lonk.from_dict(saved, world)
        self.assertFalse(dead.alive)

    def test_age_guard_survives_save_load(self):
        lonk, world = self.creature()
        lonk.age_tick()
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(lonk.to_dict(), world)
        restored.age_tick()
        self.assertEqual(restored.age, 1)


if __name__ == '__main__':
    unittest.main()
