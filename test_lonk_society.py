import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from lonk_society import Civilization, identity
from lonk_semantics import SemanticTrace
import test_lonk_dialogue as dialogue_tests


class SocietyTests(unittest.TestCase):
    def test_map_tracks_movement_growth_annexes_and_deaths(self):
        w, c, _ = self.world(3)
        room = w.lonks[0].territory
        initial = c.command('map', '')
        self.assertIn('WORLD MAP | Tick 1 | 3 living Lonks', initial)
        for lonk in w.lonks:
            self.assertIn(lonk.name, initial)
        self.assertIn('To outpost:', initial)
        c.rooms[room]['density_ticks'] = c.settings['city_ticks']
        c.settlements()
        c.rooms['Beekeeping Annex'] = dict(c.rooms[room], name='Beekeeping Annex',
                                         parent=room, display_name='Beekeeping Annex', level=0)
        c.edges['Beekeeping Annex'] = [room]
        c.edges[room].append('Beekeeping Annex')
        w.lonks[0].territory = 'Beekeeping Annex'
        w.lonks[1].alive = False
        c.schools[room] = {}
        c.rooms[room]['shrines'] = ['Holy Moss']
        c.rooms[room]['laws'] = ['sanctuary']
        current = c.command('map', '')
        self.assertIn('2 living Lonks', current)
        self.assertIn('CITY:', current)
        self.assertIn('ANNEX: Beekeeping Annex', current)
        self.assertIn('Flonk', current)
        self.assertNotIn('Plarp', current)
        self.assertIn('School', current)
        self.assertIn('Holy Moss', current)
        self.assertIn('sanctuary', current)
        self.assertIn('Paths:', current)

    @classmethod
    def setUpClass(cls):
        dialogue_tests.IntegrationTests.setUpClass()
        cls.sim = dialogue_tests.IntegrationTests.sim

    def world(self, count=4, settings=None):
        output = []
        w = SimpleNamespace(config={'civilization': settings or {}}, tick=1, lonks=[],
                            pending_births=[], max_population=20, narrate=output.append,
                            semantic_trace=SemanticTrace())
        c = Civilization(w, self.sim.TERRITORIES, self.sim.FACTIONS, self.sim.ITEM_VALUES,
                         lambda name: self.sim.Lonk(name=name, world=w, _loading=True))
        w.civilization = c
        room = next(name for name, record in c.rooms.items() if record['sacred'])
        for i in range(count):
            p = self.sim.Lonk(name=('Flonk', 'Plarp', 'Shump', 'Flip', 'Drip', 'Drop')[i], world=w, _loading=True)
            p.territory, p.faction = room, c.rooms[room]['sacred'][0]
            w.lonks.append(p)
        return w, c, output

    def test_meme_splice_requires_excited_same_faction_sacred_pair_and_is_permanent(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.vocabulary, b.vocabulary = {'beekeeping': 30}, {'jazz': 25}
        c.breed_memes()
        self.assertFalse(c.concepts)
        for p in w.lonks:
            p.state[2:4] = [0.8, 0.9]
        c.breed_memes()
        self.assertEqual(len(c.concepts), 1)
        name, axiom = next(iter(c.concepts.items()))
        self.assertIn('Beekeeping', name)
        self.assertIn('Jazz', name)
        self.assertEqual(axiom['state'], 'canon')
        self.assertIn(name, a.knowledge)
        self.assertGreater(a.will['trade'], 1)
        once = dict(a.will)
        c.apply_concepts(a)
        self.assertEqual(a.will, once)
        c.breed_memes()
        self.assertEqual(len(c.concepts), 1)

    def test_memes_do_not_form_across_factions(self):
        w, c, _ = self.world(2)
        for i, p in enumerate(w.lonks):
            p.state[2:4] = [0.9, 0.9]
            p.vocabulary = {f'token{i}': 30}
        w.lonks[1].faction = 'another faction'
        c.breed_memes()
        self.assertFalse(c.concepts)

    def test_annex_creation_has_shared_token_threshold_and_no_recursion(self):
        w, c, _ = self.world(4)
        for p in w.lonks:
            p.vocabulary = {'bees': 5, 'jazz': 4, 'void': 3}
        c.annexes()
        annexes = [r for r in c.rooms.values() if r['parent']]
        self.assertEqual(len(annexes), 1)
        self.assertEqual(len(c.extra_turns()), 1)
        self.assertIn(annexes[0]['name'], w.config['generated_locations'])
        c.annexes()
        self.assertEqual(sum(bool(r['parent']) for r in c.rooms.values()), 1)

    def test_annex_fuel_is_consumed_and_structural_anxiety_stays_lower(self):
        w, c, _ = self.world(4)
        for p in w.lonks:
            p.vocabulary = {'bees': 5, 'jazz': 4, 'void': 3}
        c.annexes()
        p = c.extra_turns()[0]
        p.items = [{'name': 'egg', 'value': 1}]
        c.begin_tick()
        self.assertFalse(p.items)
        self.assertEqual(p.structural_anxiety_reduction, 2)
        self.assertGreater(c.power_pool, 0)
        c.begin_tick()
        self.assertEqual(p.structural_anxiety_reduction, 2)

    def test_channel_mentions_raise_market_prices_exponentially_and_stay_finite(self):
        w, c, _ = self.world(2)
        portal = {'name': 'portal', 'value': 10}
        w.lonks[0].items = [portal]
        base = c.price(portal)
        c.signal(w.lonks[0], 'portal', 'speech')
        self.assertEqual(c.price(portal), base)
        for _ in range(15):
            c.signal(w.lonks[0], 'portal', 'scream')
        self.assertGreater(c.price(portal), base * 10)
        self.assertEqual(c.market['portal']['mentions'], 15)
        for _ in range(200):
            c.signal(w.lonks[0], 'portal', 'teach')
        self.assertTrue(np.isfinite(c.price(portal)))
        self.assertLessEqual(c.price(portal), base * c.settings['max_price_multiplier'])

    def test_real_whisper_and_scream_hooks_feed_market(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.items = [{'name': 'portal', 'value': 10}]
        with contextlib.redirect_stdout(io.StringIO()):
            a._verb_whisper(b, 'portal', None)
            a._verb_scream(b, 'portal', None)
        self.assertEqual(c.market['portal']['mentions'], 2)

    def test_market_heat_increases_trade_will_and_can_create_a_hunt(self):
        w, c, _ = self.world(2)
        hunter, promoter = w.lonks
        promoter.items = [{'name': 'portal', 'value': 10}]
        hunter.territory = c.edges[promoter.territory][0]
        for _ in range(15):
            c.signal(promoter, 'portal', 'whisper')
        with patch('lonk_society.random.random', return_value=0):
            intent = c.intent(hunter)
        self.assertGreater(hunter.will['trade'], 1.03)
        self.assertEqual(intent['target_name'], promoter.name)
        self.assertEqual(intent['verb'], 'seek')

    def test_market_hunt_prioritizes_the_major_promoter_over_a_richer_bystander(self):
        w, c, _ = self.world(3)
        hunter, promoter, bystander = w.lonks
        promoter.items = [{'name': 'portal', 'value': 10}]
        bystander.items = [{'name': 'portal', 'value': 10} for _ in range(3)]
        hunter.territory = c.edges[promoter.territory][0]
        hunter.personality['aggression'] = 40
        for _ in range(15):
            c.signal(promoter, 'portal', 'scream')
        c.signal(bystander, 'portal', 'whisper')
        with patch('lonk_society.random.random', return_value=0):
            intent = c.intent(hunter)
        self.assertEqual(intent['target_name'], promoter.name)

    def test_diffusion_uses_real_edit_delta_and_room_distance_excluding_control(self):
        w, c, _ = self.world(4)
        chosen, local, adjacent, control = w.lonks
        chosen.wp_role, control.wp_role = 'chosen', 'control'
        adjacent.territory = c.edges[chosen.territory][0]
        before = c.snapshot(chosen)
        local_before, adjacent_before, control_before = (p.brain.nn.b2.copy() for p in (local, adjacent, control))
        chosen.brain.nn.b2[1] += 2
        c.diffuse_edit(chosen, before)
        c.diffuse()
        self.assertAlmostEqual(local.brain.nn.b2[1] - local_before[1], 0.5)
        np.testing.assert_array_equal(adjacent.brain.nn.b2, adjacent_before)
        np.testing.assert_array_equal(control.brain.nn.b2, control_before)
        c.diffuse()
        self.assertAlmostEqual(adjacent.brain.nn.b2[1] - adjacent_before[1], 0.25)
        c.diffuse()
        self.assertAlmostEqual(local.brain.nn.b2[1] - local_before[1], 0.5)

    def test_martyrdom_locks_last_words_and_creates_a_real_shrine_cult(self):
        w, c, _ = self.world(4)
        martyr = w.lonks[0]
        martyr.last_spoken = 'beekeeping dad'
        for p in w.lonks[1:]:
            p.emotion['anxiety'] = 80
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.random, 'random', return_value=0.99):
            martyr.die()
        self.assertIn('dad', c.holy)
        self.assertEqual(c.holy['dad']['utterance'], 'beekeeping dad')
        self.assertTrue(c.rooms[martyr.territory]['shrines'])
        cult = c.rooms[martyr.territory]['shrines'][0]
        self.assertEqual(w.lonks[1].faction, cult)
        self.assertGreaterEqual(w.lonks[1].trance_until, w.tick)
        follower = w.lonks[1]
        with contextlib.redirect_stdout(io.StringIO()):
            follower.perform_ritual()
            follower.create_myth()
            follower._verb_preach(w.lonks[2], None, None)
            restored = self.sim.Lonk.from_dict(follower.to_dict(), world=w)
        self.assertEqual(restored.religion, follower.religion)

    def test_blasphemy_splits_followers_and_records_a_bounded_civil_war(self):
        w, c, _ = self.world(4)
        martyr = w.lonks[0]
        martyr.last_spoken = 'beekeeping dad'
        for p in w.lonks[1:]:
            p.emotion['anxiety'] = 80
        martyr.alive = False
        c.on_death(martyr)
        c.command('blaspheme', f'"{martyr.territory}" "dad denies the bees"')
        self.assertEqual(len(c.wars), 1)
        self.assertEqual(len({p.faction for p in c.living()}), 2)
        self.assertEqual(c.wars[0]['until'], w.tick + 30)

    def test_repeated_martyr_words_can_build_a_second_shrine_without_duplicate_cults(self):
        w, c, _ = self.world(4)
        first, second = w.lonks[:2]
        room = first.territory
        for p in w.lonks:
            p.emotion['anxiety'] = 80
        first.last_spoken = 'beekeeping dad'
        first.alive = False
        c.on_death(first)
        second.territory = c.edges[room][0]
        second.last_spoken = 'beekeeping dad'
        second.alive = False
        c.on_death(second)
        self.assertEqual(c.metrics['cults'], 1)
        self.assertTrue(c.rooms[room]['shrines'])
        self.assertEqual(c.rooms[room]['shrines'], c.rooms[second.territory]['shrines'])

    def test_romance_requires_four_primary_ticks_then_following_overrides_other_business(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        for p in w.lonks:
            p.state[2] = 0.8
        for _ in range(3):
            c.romance()
        self.assertFalse(getattr(a, 'romance_partner', None))
        c.romance()
        self.assertEqual(a.romance_partner, identity(b))
        b.territory = c.edges[a.territory][0]
        intent = c.intent(a)
        self.assertEqual(intent['verb'], 'follow')
        c.act(a, 'follow', b, None)
        self.assertEqual(a.territory, b.territory)

    def test_crush_gifts_the_best_item_without_ping_pong(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.items = [{'name': 'portal', 'value': 20}, {'name': 'egg', 'value': 1}]
        c.pair(a, b)
        intent = c.intent(a)
        self.assertEqual(intent['object']['name'], 'portal')
        with contextlib.redirect_stdout(io.StringIO()):
            c.act(a, intent['verb'], b, intent['object'])
        self.assertEqual(b.items[0]['name'], 'portal')
        other = c.intent(b)
        self.assertTrue(other is None or other['verb'] != 'devote')

    def test_jealous_rival_and_heartbreak_produce_actual_state_changes(self):
        w, c, _ = self.world(3)
        a, b, rival = w.lonks
        c.pair(a, b)
        rival.personality['aggression'] = 90
        intent = c.intent(a)
        self.assertEqual(intent['verb'], 'jealous')
        self.assertEqual(a.jealousy['rival'], identity(rival))
        c.breakup(a, 'the bees whispered betrayal')
        self.assertIsNone(a.crush)
        self.assertIsNone(b.crush)
        self.assertGreaterEqual(a.trauma, 25)
        self.assertTrue(any(t.get('kind') == 'heartbreak' for t in a.inner_thoughts))

    def test_baby_splices_parents_and_neural_weights_with_a_birth_cooldown(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        c.rooms[a.territory]['vibe'] = 'soft and emotionally supportive'
        a.vocabulary, b.vocabulary = {'bees': 9, 'dad': 7}, {'jazz': 8, 'void': 6}
        a.brain.nn.b2[:] = 0.5; b.brain.nn.b2[:] = 1.5
        a.emotion['joy'] = b.emotion['joy'] = 100
        c.pair(a, b)
        c.births()
        self.assertEqual(len(w.pending_births), 1)
        baby = w.pending_births[0]
        self.assertEqual(baby.name, 'Flarp')
        self.assertEqual(baby.generation, 2)
        np.testing.assert_array_equal(baby.brain.nn.b2, np.ones(6))
        self.assertEqual(set(baby.vocabulary), {'bees', 'dad', 'jazz', 'void'})
        c.births()
        self.assertEqual(len(w.pending_births), 1)
        w.lonks.append(w.pending_births.pop())
        c.command('engineer', f'{baby.name} explore 2')
        self.assertEqual(baby.brain.nn.b2[1], 2)

    def test_birth_respects_capacity(self):
        w, c, _ = self.world(2)
        w.max_population = 2
        c.rooms[w.lonks[0].territory]['vibe'] = 'supportive'
        for p in w.lonks:
            p.emotion['joy'] = 100
        c.pair(*w.lonks)
        c.births()
        self.assertFalse(w.pending_births)

    def test_schools_copy_headmaster_beliefs_and_subversion_chants_on_next_turn(self):
        w, c, _ = self.world(3)
        head = w.lonks[0]
        head.emotion['wisdom'] = 99
        head.vocabulary = {'beekeeping': 8}
        head.knowledge = {'beekeeping'}
        head.axioms = [{'feature': 'health:high', 'outcome': 'reward:up', 'hits': 8, 'misses': 0, 'state': 'canon'}]
        head.paradigm = 'what do the bees know?'
        c.rooms[head.territory]['level'] = 1
        c.classrooms()
        for student in w.lonks[1:]:
            self.assertEqual(student.vocabulary, head.vocabulary)
            self.assertEqual(student.axioms, head.axioms)
            self.assertIsNot(student.axioms, head.axioms)
            self.assertEqual(student.paradigm, head.paradigm)
        c.command('subvert', f'{head.name} pickle')
        for p in w.lonks:
            intention = c.intent(p)
            self.assertEqual(intention['verb'], 'proclaim')
            self.assertEqual(intention['object'], 'I am Pickle Rick!')

    def test_extortion_conserves_items_and_records_anxiety_damage(self):
        w, c, _ = self.world(2)
        scammer, victim = w.lonks
        scammer.personality['aggression'] = 95
        victim.emotion['anxiety'] = 95
        scammer.items = [{'name': 'worthless pebble', 'value': 0}]
        victim.items = [{'name': "Warrior's Shield", 'value': 20}]
        with patch('lonk_society.random.random', return_value=0):
            self.assertTrue(c.extort(scammer, victim))
        self.assertEqual(scammer.items[0]['name'], "Warrior's Shield")
        self.assertEqual(victim.items[0]['name'], 'worthless pebble')
        self.assertGreater(victim.trauma, 0)

    def test_fair_trade_compensation_tax_and_broker_controls(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.items, b.items = [{'name': 'egg', 'value': 1}], [{'name': 'portal', 'value': 20}]
        self.assertFalse(c.trade(a, b))
        a.coins, b.coins = 100, 100
        c.command('tax', '0.1')
        self.assertTrue(c.trade(a, b))
        self.assertAlmostEqual(a.coins + b.coins + c.treasury['coins'], 200)
        self.assertGreater(c.treasury['coins'], 0)
        c.command('confiscate', f'{a.name} portal')
        self.assertEqual(c.treasury['items'][0]['name'], 'portal')
        c.command('back', f'{a.name} portal')
        a.items.clear()
        c.begin_tick()
        self.assertTrue(any(i['name'] == 'portal' for i in a.items))

    def test_cashless_trader_can_monetize_an_item_and_later_buy_without_barter(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.items = [{'name': 'seed', 'value': 3}]
        b.items = [{'name': 'shield', 'value': 8}]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(c.trade(a, b))
        self.assertFalse(a.items)
        self.assertEqual(a.coins, 3)
        # Additional reserves are explicit currency, not a fabricated barter item.
        a.coins = 10
        c.tax_rate = 0.1
        self.assertTrue(c.trade(a, b))
        self.assertEqual(a.items[0]['name'], 'shield')
        self.assertAlmostEqual(a.coins + b.coins + c.treasury['coins'], 10)
        self.assertEqual(c.metrics['cash_trades'], 1)

    def test_settlement_perks_do_not_stack_on_reentry_and_laws_have_sources(self):
        w, c, _ = self.world(3, {'settlement_ticks': 1, 'city_ticks': 2})
        room = w.lonks[0].territory
        c.concepts['The Sacred Bee Pit'] = {'effects': {'trade': 1.02}, 'state': 'canon'}
        for p in w.lonks:
            p.cultural_concepts = ['The Sacred Bee Pit']
        c.settlements()
        self.assertEqual(c.rooms[room]['level'], 1)
        self.assertEqual(w.lonks[0].max_health, 120)
        c.on_enter(w.lonks[0]); c.on_enter(w.lonks[0])
        self.assertEqual(w.lonks[0].max_health, 120)
        c.settlements()
        self.assertEqual(c.rooms[room]['level'], 2)
        self.assertEqual(c.rooms[room]['law_source'], 'The Sacred Bee Pit')
        self.assertTrue(c.rooms[room]['laws'])

    def test_dropped_items_can_found_an_outpost(self):
        w, c, _ = self.world(1)
        room = w.lonks[0].territory
        w.lonks[0].items = [{'name': f'seed {i}', 'value': 1} for i in range(6)]
        for item in list(w.lonks[0].items):
            c.command('drop', f'{w.lonks[0].name} "{item["name"]}"')
        c.settlements()
        self.assertEqual(c.rooms[room]['level'], 1)

    def test_city_laws_change_school_admission_and_protect_against_scams(self):
        w, c, _ = self.world(3)
        room = w.lonks[0].territory
        for i, p in enumerate(w.lonks):
            p.faction = f'group {i}'
        c.rooms[room]['level'] = 1
        c.classrooms()
        self.assertFalse(c.schools)
        c.rooms[room]['laws'] = ['open_school']
        c.classrooms()
        self.assertEqual(len(c.schools[room]['students']), 2)
        a, b = w.lonks[:2]
        a.items = [{'name': 'worthless pebble', 'value': 0}]
        b.items = [{'name': 'portal', 'value': 20}]
        c.rooms[room]['laws'] = ['fair_trade']
        self.assertFalse(c.extort(a, b))
        self.assertEqual(b.items[0]['name'], 'portal')

    def test_romance_vector_and_city_perks_survive_agent_save(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        c.pair(a, b)
        c.rooms[a.territory]['level'] = 1
        c.on_enter(a)
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(a.to_dict(), world=w)
        self.assertEqual(restored.affinity_vector, a.affinity_vector)
        self.assertEqual(restored.romance_partner, identity(b))
        self.assertEqual(restored.max_health, 120)
        self.assertEqual(restored.city_blessings, a.city_blessings)

    def test_manual_tune_emits_wave_but_rejects_control(self):
        w, c, _ = self.world(2)
        a, b = w.lonks
        a.wp_role, b.wp_role = 'chosen', 'control'
        c.command('tune', f'{a.name} explore 1.5')
        self.assertEqual(a.brain.nn.b2[1], 1.5)
        self.assertEqual(len(c.waves), 1)
        before = b.brain.nn.b2.copy()
        with self.assertRaises(ValueError):
            c.command('tune', f'{b.name} explore 1.5')
        np.testing.assert_array_equal(before, b.brain.nn.b2)

    def test_generated_state_roundtrips_as_plain_json(self):
        w, c, _ = self.world(4)
        for p in w.lonks:
            p.vocabulary = {'bees': 5, 'jazz': 4, 'void': 3}
        c.annexes()
        c.command('back', f'{w.lonks[0].name} portal')
        data = json.loads(json.dumps(c.to_dict(), allow_nan=False))
        restored = Civilization(w, self.sim.TERRITORIES, self.sim.FACTIONS, self.sim.ITEM_VALUES, c.factory)
        restored.restore(data)
        self.assertEqual(restored.to_dict(), data)

    def test_live_programmer_hook_creates_diffusion_wave(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w = self.sim.LonkWorld(num_lonks=3)
        w.semantic_trace = SemanticTrace()
        chosen = next(p for p in w.lonks if p.wp_role == 'chosen')
        control = next(p for p in w.lonks if p.wp_role == 'control')
        before = control.brain.nn.b2.copy()
        class Programmer:
            name = 'Test programmer'
            def program(self, lonk):
                lonk.brain.nn.b2[1] += 1
                return 'exploration patch'
        w.programmer = Programmer()
        with contextlib.redirect_stdout(io.StringIO()):
            w.weight_programming_step()
            w.civilization.diffuse()
        self.assertEqual(w.civilization.metrics['diffusion_waves'], 1)
        np.testing.assert_array_equal(control.brain.nn.b2, before)

    def test_player_commands_route_through_help_and_do_not_overwrite_a_real_save(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w = self.sim.LonkWorld(num_lonks=3)
        w.semantic_trace = SemanticTrace()
        a, b, _ = w.lonks
        output, errors = io.StringIO(), io.StringIO()
        commands = ['/help', '/society', f'/matchmake {a.name} {b.name}', f'/heartbreak {a.name} bees',
                    f'/back {a.name} portal', f'/interact {a.name} scream portal', '/market', '/tax 0.1',
                    f'/confiscate {a.name} portal', '/tax nan', 'quit']
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), patch('builtins.input', side_effect=commands), patch.object(w, 'save') as save:
            w.interactive_loop()
        self.assertIn('/matchmake', output.getvalue())
        self.assertIn('Trade tax set', output.getvalue())
        self.assertIn('Command error', output.getvalue())
        self.assertNotIn('Traceback', errors.getvalue())
        self.assertEqual(w.civilization.market['portal']['mentions'], 1)
        save.assert_called_once()

    def test_invalid_commands_and_nonfinite_settings_do_not_mutate_weights(self):
        w, c, _ = self.world(2)
        chosen = w.lonks[0]
        chosen.wp_role = 'chosen'
        before = chosen.brain.nn.b2.copy()
        with self.assertRaises(ValueError):
            c.command('tune', f'{chosen.name} explore nan')
        np.testing.assert_array_equal(before, chosen.brain.nn.b2)
        with self.assertRaises(ValueError):
            c.command('matchmake', chosen.name)
        w.config['civilization'] = {'diffusion_rate': float('inf')}
        with self.assertRaises(ValueError):
            Civilization(w, self.sim.TERRITORIES, self.sim.FACTIONS, self.sim.ITEM_VALUES, c.factory)

    def test_real_annex_scheduler_grants_at_most_two_acts(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w = self.sim.LonkWorld(num_lonks=2)
        w.semantic_trace = SemanticTrace()
        w.programmer, w.dream_chance = None, 0
        c = w.civilization
        parent = next(iter(c.rooms))
        annex = parent + ' / Test Annex'
        c.rooms[annex] = {**copy.deepcopy(c.rooms[parent]), 'name': annex, 'parent': parent}
        a, b = w.lonks
        a.territory, b.territory = annex, parent
        with contextlib.redirect_stdout(io.StringIO()), patch.object(a, 'act') as fast, patch.object(b, 'act') as normal, patch.object(a, 'choose_action', return_value='idle'), patch.object(b, 'choose_action', return_value='idle'):
            w.world_tick()
        self.assertEqual(fast.call_count, 2)
        self.assertEqual(normal.call_count, 1)

    def test_ordinary_arrivals_cannot_overfill_the_new_birth_capacity(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w = self.sim.LonkWorld(num_lonks=1)
        w.semantic_trace = SemanticTrace()
        w.programmer, w.dream_chance, w.arrival_chance = None, 0, 1
        w.max_population, w.starting_population = 1, 5
        lonk = w.lonks[0]
        with contextlib.redirect_stdout(io.StringIO()), patch.object(lonk, 'act'), patch.object(lonk, 'choose_action', return_value='idle'):
            w.world_tick()
        self.assertFalse(w.pending_births)


if __name__ == '__main__':
    unittest.main()
