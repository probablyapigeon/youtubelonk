"""Live terminal/event integration and spatial simulation regressions."""
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lonk_live import TerminalWorldView, event_details
from lonk_visuals import body_for, display_width
import test_lonk_map as maps
import test_lonk_society as societies


class LiveViewTests(unittest.TestCase):
    def view(self, width=100, height=32):
        c = maps.society()
        c.world.civilization = c
        c.world.tts_enabled = False
        output = io.StringIO()
        view = TerminalWorldView(c.world, output, size=(width, height))
        view.enabled = True
        return c, view, output

    def test_event_links_exact_actors_rooms_and_marker(self):
        c, view, _ = self.view()
        c.world.lonks[1].territory = 'Moss'
        details = event_details(c.world, 'Grorp attacks Krip!', view.positions)
        self.assertEqual([p.name for p in details['actors']], ['Grorp', 'Krip'])
        self.assertEqual(details['rooms'], ['Moss'])
        self.assertIn('[1] Moss', details['prefix'])
        self.assertEqual(details['marker'], '⚔️')
        self.assertEqual(event_details(c.world, 'Grorp22 attacks nobody!', view.positions)['actors'], [])

    def test_bubble_reveals_only_typed_speech_then_clears(self):
        c, view, _ = self.view()
        c.world.lonks[1].territory = 'Moss'
        text = '💬 Grorp → Krip: The moss is very shiny.'
        view.begin_event(text)
        view.current = '💬 Grorp → Krip: The moss'
        graph, _ = view._map(99, 32)
        early = '\n'.join(graph)
        self.assertIn('╭', early)
        self.assertIn('▶', early)
        self.assertIn('The moss', early)
        self.assertNotIn('very shiny', early)
        view.current = text
        graph, _ = view._map(99, 32)
        self.assertIn('shiny.', '\n'.join(graph))
        self.assertEqual(view.event['speech']['speaker'].name, 'Grorp')
        view.end_event()
        graph, _ = view._map(99, 32)
        self.assertNotIn('╭', '\n'.join(graph))
        self.assertIn('The moss is very shiny.', view.feed[-1])

    def test_actions_do_not_get_speech_bubbles(self):
        c, view, _ = self.view()
        for text in ('Grorp attacks Krip!', 'Grorp discovers a Crystal Shard!',
                     "Grorp teaches Krip the word 'moss'"):
            self.assertIsNone(event_details(c.world, text, view.positions)['speech'])

    def test_long_emoji_speech_wraps_and_keeps_feed_and_prompt_visible(self):
        for width, height in ((41, 18), (60, 24), (80, 24), (100, 32), (140, 40)):
            with self.subTest(width=width, height=height):
                c, view, output = self.view(width, height)
                text = '💬 Grorp → Player: '+('🧑🏽‍🚀 moss is wonderful. '*20)+'finalword'
                view.begin_event(text)
                view.current = text
                view.draw(force=True)
                frame = output.getvalue().rsplit('\x1b[H', 1)[-1]
                frame = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', frame)
                self.assertLessEqual(len(frame.splitlines()), height-1)
                self.assertTrue(all(display_width(line) <= width-1 for line in frame.splitlines()))
                graph, _ = view._map(width-1, height)
                self.assertIn('finalword', '\n'.join(graph))
                self.assertLessEqual(sum('│' in row for row in graph), 3)

    def test_quoted_names_and_actions_are_not_live_participants(self):
        c, view, _ = self.view()
        details = event_details(c.world, 'Grorp → Player: Krip attacks everyone!', view.positions)
        self.assertEqual([p.name for p in details['actors']], ['Grorp'])
        self.assertEqual(details['rooms'], ['Moss'])
        self.assertEqual(details['marker'], '💬')

    def test_feed_updates_in_place_and_leaves_prompt_row(self):
        c, view, output = self.view(80, 24)
        view.begin_tick()
        with patch('lonk_live.time.sleep'):
            view.narrate('Grorp says: moss is excellent!', lambda: print('Grorp says: moss is excellent!'))
        view.finish_tick()
        frame = output.getvalue().rsplit('\x1b[H', 1)[-1]
        frame = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', frame)
        self.assertLessEqual(len(frame.splitlines()), 23)
        self.assertTrue(all(display_width(line) <= 79 for line in frame.splitlines()))
        self.assertIn('moss is excellent!', frame)
        self.assertEqual(len(view.feed), 1)
        self.assertIn(body_for(c.world.lonks[0])+' Grorp', view.feed[0])
        self.assertTrue(output.getvalue().endswith('\x1b[?25h'))

    def test_moving_body_uses_real_trail_then_arrives(self):
        c, view, _ = self.view()
        actor = c.world.lonks[0]
        actor.territory = 'Pit'
        view.begin_event('Grorp moves from Moss to Pit.')
        self.assertEqual(view.event['travel'], (actor, 'Moss', 'Pit'))
        self.assertEqual(view.event['rooms'], ['Moss', 'Pit'])
        view.current = 'Grorp moves'
        graph, _ = view._map(99, 32)
        self.assertIn(body_for(actor), '\n'.join(graph))
        view.end_event()
        self.assertEqual(view.positions['Grorp'], 'Pit')
        self.assertEqual(view.last_event['marker'], '🚶')

    def test_trade_marker_moves_between_bodies_in_the_shared_room(self):
        c, view, _ = self.view()
        c.world.lonks[1].territory = 'Moss'
        view.begin_event('Grorp gives Crystal Shard to Krip!')
        view.current = 'Grorp'
        early, _ = view._map(99, 32)
        view.current = 'Grorp gives Crystal Shard to Krip!'
        late, _ = view._map(99, 32)
        early_bar = next(line for line in early if '🎁' in line and body_for(c.world.lonks[0]) in line)
        late_bar = next(line for line in late if '🎁' in line and body_for(c.world.lonks[0]) in line)
        self.assertNotEqual(early_bar, late_bar)
        self.assertIn(body_for(c.world.lonks[0]), late_bar)
        self.assertIn(body_for(c.world.lonks[1]), late_bar)

    def test_annex_pages_keep_global_room_numbers(self):
        c, view, _ = self.view(80, 24)
        for i in range(8):
            name = f'Annex{i}'
            c.rooms[name] = {'parent': 'Moss', 'level': 0, 'dropped': []}
            c.edges[name] = ['Moss']
            c.edges['Moss'].append(name)
        c.world.lonks[0].territory = 'Annex7'
        view.begin_event('Grorp says hello!')
        graph, page = view._map(79, 24)
        self.assertIn('of 14', page)
        self.assertIn('[14]', '\n'.join(graph))
        self.assertIn('Annex7', '\n'.join(graph))
        self.assertIn('[14] Annex7', view.event['prefix'])

    def test_reset_discards_old_actor_references_and_history(self):
        c, view, _ = self.view()
        view.begin_event('Grorp says hello!')
        view.end_event()
        c.world.lonks[0].territory = 'Bush'
        view.reset()
        self.assertFalse(view.feed)
        self.assertIsNone(view.last_event)
        self.assertEqual(view.positions['Grorp'], 'Bush')


class SpatialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        societies.SocietyTests.setUpClass()
        cls.sim = societies.SocietyTests.sim

    def world(self):
        original, c, messages = societies.SocietyTests().world(3)
        w = self.sim.LonkWorld.__new__(self.sim.LonkWorld)
        w.__dict__.update(original.__dict__)
        del w.__dict__['narrate']  # Exercise the real world narrator, not fixture collection.
        w.tts_enabled, w.tts_engine, w.tts_running = False, None, False
        c.world = w
        for p in w.lonks:
            p.world = w
        output = io.StringIO()
        w._live_view = TerminalWorldView(w, output, size=(100, 32))
        w._live_view.enabled = True
        return w, c, output

    def test_tick_print_and_narration_share_one_feed(self):
        w, _, output = self.world()
        def tick():
            w.tick += 1
            print('Flonk finds moss!')
            w.narrate('Plarp says hello!')
        w._advance_world_tick = tick
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), patch('lonk_live.time.sleep'):
            w.world_tick()
            print('Press ENTER')
        self.assertEqual(len(w._live_view.feed), 2)
        self.assertEqual(stdout.getvalue(), 'Press ENTER\n')
        self.assertIn('Plarp says hello!', w._live_view.feed[-1])
        self.assertTrue(output.getvalue().endswith('\x1b[?25h'))

    def test_live_tts_receives_only_original_text_once(self):
        w, _, _ = self.world()
        w.tts_enabled, w.tts_engine = True, object()
        spoken = []
        def speak(name, text, completed=None, **kwargs):
            spoken.append(text)
            completed.set()
        w.speak = speak
        w._advance_world_tick = lambda: print('Flonk says hello!')
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.time, 'sleep'):
            w.world_tick()
        self.assertEqual(spoken, ['Flonk says hello!'])
        self.assertEqual(len(w._live_view.feed), 1)
        self.assertIn('Flonk says hello!', w._live_view.feed[0])

    def test_bubble_uses_existing_speech_stream_without_duplicate_voice(self):
        w, _, screen = self.world()
        w.tts_enabled, w.tts_engine = True, object()
        spoken = []
        def speak(name, text, completed=None, **kwargs):
            spoken.append(text)
            completed.set()
        w.speak = speak
        text = '💬 Flonk → Plarp: I found some shiny moss!'
        w._advance_world_tick = lambda: w.narrate(text)
        with contextlib.redirect_stdout(io.StringIO()), patch.object(self.sim.time, 'sleep'):
            w.world_tick()
        self.assertEqual(spoken, [text])
        self.assertIn('╭', screen.getvalue())
        self.assertIn('shiny moss!', w._live_view.feed[-1])
        self.assertEqual(len(w._live_view.feed), 1)

    def test_auto_interrupt_returns_to_prompt_then_gift_and_quit(self):
        w, _, screen = self.world()
        w.auto_mode, w.auto_speed, w.tts_error = True, 1, None
        w.command_parser = self.sim.CommandParser()
        w.save, w._stop_tts_thread = Mock(), Mock()
        w._advance_world_tick = Mock(side_effect=KeyboardInterrupt)
        commands = iter(['gift Flonk portal', 'quit'])
        def read(prompt):
            self.assertFalse(w.auto_mode)
            self.assertIsNone(w._live_active)
            self.assertFalse(w._narrating_live if hasattr(w, '_narrating_live') else False)
            self.assertTrue(screen.getvalue().endswith('\x1b[?25h'))
            return next(commands)
        console = io.StringIO()
        with contextlib.redirect_stdout(console), patch('builtins.input', side_effect=read), patch.object(self.sim.time, 'sleep'):
            w.interactive_loop()
        self.assertIn('Auto mode paused.', console.getvalue())
        self.assertNotIn('Error:', console.getvalue())
        self.assertIn('portal', str(w.lonks[0].items))
        w.save.assert_called_once()

    def test_interrupt_restores_cursor_stdout_and_live_flags(self):
        w, _, output = self.world()
        w._advance_world_tick = Mock(side_effect=KeyboardInterrupt)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(KeyboardInterrupt):
            w.world_tick()
        self.assertIsNone(w._live_active)
        self.assertTrue(output.getvalue().endswith('\x1b[?25h'))

    def test_gift_command_updates_inventory_and_feed_without_a_tick(self):
        w, _, _ = self.world()
        tick = w.tick
        with patch('lonk_live.time.sleep'), w.live_command_output():
            result = w.lonks[0].receive_gift('portal')
            print('Player gifts Flonk a portal. '+result)
        self.assertEqual(w.tick, tick)
        self.assertIn('portal', str(w.lonks[0].items).lower())
        self.assertIn('portal', w._live_view.feed[-1])
        self.assertIsNone(w._live_active)

    def test_real_save_load_resets_dashboard_without_serializing_it(self):
        with contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as folder:
            w = self.sim.LonkWorld(num_lonks=2)
            view = w._live_view = TerminalWorldView(w, io.StringIO(), size=(100, 32))
            view.enabled = True
            view.feed.append('old world event')
            saved_names = [p.name for p in w.lonks]
            path = str(Path(folder)/'world.json')
            w.save(path)
            self.assertNotIn('_live_view', Path(path).read_text())
            w.lonks.clear()
            self.assertTrue(w.load(path))
            self.assertEqual([p.name for p in w.lonks], saved_names)
            self.assertFalse(view.feed)
            self.assertEqual(set(view.positions), set(saved_names))

    def test_remote_interaction_walks_one_edge_instead_of_healing_across_map(self):
        w, c, _ = self.world()
        w.narrate = Mock()
        names = list(c.rooms)
        actor, target, nearby = w.lonks
        actor.territory = nearby.territory = names[0]
        target.territory, target.health = names[2], 40
        self.assertEqual(actor.nearby_lonks(), [nearby])
        old = actor.territory
        result = actor.execute_action({'verb': 'help', 'target_type': 'other', 'target_name': target.name})
        self.assertTrue(result['travelling'])
        self.assertIn(actor.territory, c.edges[old])
        self.assertNotEqual(actor.territory, target.territory)
        self.assertEqual(target.health, 40)

    def test_remote_trade_fight_speech_and_gifts_have_no_remote_effects(self):
        w, c, _ = self.world()
        w.narrate = Mock()
        a, b = w.lonks[:2]
        a.territory, b.territory = list(c.rooms)[:2]
        a.items = [{'name': 'egg'}]
        b.items = [{'name': 'pickle'}]
        health = b.health
        a.rival = b
        a.duel()
        self.assertEqual(b.health, health)
        self.assertFalse(c.trade(a, b))
        self.assertFalse(a._verb_give(b, a.items[0], None)['success'])
        self.assertFalse(a._verb_bonk(b, None, None)['success'])
        self.assertFalse(a._verb_teach(b, 'moss', None)['success'])
        self.assertEqual(a.speak('hello', b), '')
        w.narrate.assert_not_called()

    def test_wandering_and_disconnected_paths_do_not_teleport(self):
        w, c, _ = self.world()
        w.narrate = Mock()
        actor = w.lonks[0]
        names = list(c.rooms)
        actor.territory = names[0]
        self.assertFalse(c.move(actor, names[3]))
        with patch.object(self.sim.random, 'choice', side_effect=lambda options: options[0]):
            actor.wander()
        self.assertIn(actor.territory, c.edges[names[0]])
        c.edges = {name: [] for name in names}
        self.assertEqual(c.next_room(names[0], names[3]), names[0])


if __name__ == '__main__':
    unittest.main()
