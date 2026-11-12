"""TTS regression checks without changing saved worlds or requiring speakers."""
import importlib.util
import queue
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('dynamiclonk', 'dynamiclonk-py-v13-lonks-finally-have-ears-say-command-fixed.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SpeechTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(mod.time, 'sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def world(self):
        world = mod.LonkWorld.__new__(mod.LonkWorld)
        world.tts_enabled = False
        world.tts_engine = None
        world.tts_queue = queue.Queue()
        world.tts_thread = None
        world.tts_running = False
        world.tts_ready = threading.Event()
        world.tts_error = None
        return world

    def test_engine_thread_and_repeated_speech(self):
        world = self.world()
        calls = []
        class Engine:
            def setProperty(self, *args): pass
            def say(self, text):
                calls.append((text, threading.get_ident()))
            def runAndWait(self): pass
            def stop(self): pass
        def initialize():
            calls.append(('init', threading.get_ident()))
            return Engine()
        with patch.object(mod.sys, 'platform', 'linux'), patch.object(mod.pyttsx3, 'init', initialize):
            self.assertTrue(world._start_tts_thread())
            world.tts_enabled = True
            world.speak('Alice', 'hello')
            world.speak('Bob', 'hello again')
            world.tts_queue.join()
            world._stop_tts_thread()
        self.assertEqual([c[0] for c in calls], ['init', 'Alice: hello', 'Bob: hello again'])
        self.assertEqual(len({c[1] for c in calls}), 1)
        self.assertNotEqual(calls[0][1], threading.get_ident())
        self.assertFalse(world.tts_thread.is_alive())

    def test_initialization_failure_is_reported(self):
        world = self.world()
        with patch.object(mod.sys, 'platform', 'linux'), patch.object(mod.pyttsx3, 'init', side_effect=RuntimeError('voice unavailable')):
            self.assertFalse(world._start_tts_thread())
        self.assertEqual(world.tts_error, 'voice unavailable')
        world._stop_tts_thread()

    def test_lonk_speech_reaches_world(self):
        from unittest.mock import Mock
        lonk = mod.Lonk.__new__(mod.Lonk)
        lonk.name = 'Alice'
        lonk.world = Mock()
        lonk.speak('hello')
        lonk.world.narrate.assert_called_once_with('\U0001f4ac Alice: hello')

    def test_narration_prints_once_per_spoken_line(self):
        import contextlib
        import io
        world = self.world()
        spoken = []
        class Engine:
            def setProperty(self, *args): pass
            def say(self, text): spoken.append(text)
            def runAndWait(self): pass
            def stop(self): pass
        output = io.StringIO()
        lines = ["Sharp BONKS Krob!", "Sharp teaches Brob the verb 'teach'",
                 "Sharp \u2192 Brob: Let me process that.",
                 "Drump whispers to Krob: 'Sharp stole my favorite rock.'",
                 "? Krob has developed a catchphrase: 'I crave moss.'"]
        with contextlib.redirect_stdout(output), patch.object(mod.sys, 'platform', 'linux'), patch.object(mod.pyttsx3, 'init', return_value=Engine()):
            self.assertTrue(world._start_tts_thread())
            world.tts_enabled = True
            for line in lines:
                world.narrate(line)
            world.tts_queue.join()
            world._stop_tts_thread()
        self.assertEqual(output.getvalue().splitlines(), lines)
        self.assertEqual(len(spoken), len(lines))
        self.assertIn("Sharp BONKS Krob!", spoken)

    def test_disabled_narration_prints_without_queueing(self):
        import contextlib
        import io
        world = self.world()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            world.narrate('Sharp BONKS Krob!')
        self.assertEqual(output.getvalue(), 'Sharp BONKS Krob!\n')
        self.assertTrue(world.tts_queue.empty())

    def test_tick_voices_prints_and_narration_once_in_order(self):
        import contextlib
        import io
        world = self.world()
        world.tts_enabled = True
        world.tts_engine = object()
        spoken = []
        def speak(name, line, completed=None, **kwargs):
            spoken.append(line)
            completed.set()
            return True
        world.speak = speak
        def tick():
            print('A new Lonk emerges!')
            print('Found ', end='')
            print('a shiny!')
            world.narrate('Hello there!')
            print('A ritual happens.\nA room changes.')
        world._advance_world_tick = tick
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            world.world_tick()
            print('Press ENTER')
        expected = ['A new Lonk emerges!', 'Found a shiny!', 'Hello there!',
                    'A ritual happens.', 'A room changes.']
        self.assertEqual(spoken, expected)
        self.assertEqual(output.getvalue().splitlines(), expected + ['Press ENTER'])

    def test_tick_restores_output_after_interrupt(self):
        import contextlib
        import io
        from unittest.mock import Mock
        world = self.world()
        world.tts_enabled = True
        world.tts_engine = object()
        world._advance_world_tick = Mock(side_effect=KeyboardInterrupt)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(KeyboardInterrupt):
                world.world_tick()
            self.assertIs(mod.sys.stdout, output)

    def test_map_prints_after_tick_without_being_spoken(self):
        import contextlib
        import io
        from unittest.mock import Mock
        for enabled in (False, True):
            world = self.world()
            world.tts_enabled = enabled
            world.tts_engine = object() if enabled else None
            world.civilization = Mock()
            world.civilization.command.return_value = 'WORLD MAP | Tick 1'
            world._advance_world_tick = lambda: world.narrate('Lonk moves.')
            spoken = []
            def speak(name, line, completed=None, **kwargs):
                spoken.append(line)
                completed.set()
            world.speak = speak
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                world.world_tick()
            self.assertEqual(output.getvalue().splitlines(), ['Lonk moves.', 'WORLD MAP | Tick 1'])
            self.assertEqual(spoken, ['Lonk moves.'] if enabled else [])

    def test_commands_remain_responsive_while_speech_is_pending(self):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest.mock import Mock
        world = self.world()
        world.auto_mode = False
        world.tick = 10
        world.command_parser = mod.CommandParser()
        world.tts_engine = object()
        world.tts_enabled = True
        world.save = Mock()
        world.world_tick = Mock(side_effect=lambda: world.narrate('Alice BONKS Bob!'))
        alice = SimpleNamespace(name='Alice', health=50, age=0, lifespan=90, emotion={'joy': 20},
            state=[0.5, 0.5, 0.2, 0.3, 0.1], trauma=0,
            personality={}, memory={'events': []}, gossip=[], alive=True,
            generation=1, faction=None, territory=None,
            get_xembra_state=lambda: 'peaceful',
            respond_to_player=Mock(return_value='hello back'), hear=Mock(),
            receive_gift=Mock(return_value='Alice feels better'))
        world.lonks = [alice]
        alice.seed_rumor = lambda source, rumor: alice.gossip.append((source, 'rumor', rumor, 3))
        commands = iter(['', '/help', 'observe Alice', '/say Alice hello',
                         '/listen Alice', '/interact Alice greet',
                         'gift Alice joy', '/gossip hello', 'stats', 'quit'])
        output = io.StringIO()
        prompts = []
        def read(prompt):
            prompts.append(prompt)
            # All narration must already be visible before input starts.
            if len(prompts) == 2:
                self.assertIn('Alice BONKS Bob!', output.getvalue())
            return next(commands)
        with contextlib.redirect_stdout(output), patch('builtins.input', side_effect=read):
            world.interactive_loop()
        self.assertEqual(len(prompts), 10)
        self.assertTrue(all(p == 'Press ENTER to advance, or type a command: ' for p in prompts))
        self.assertIn('LEGACY COMMANDS', output.getvalue())
        self.assertIn('OBSERVING Alice', output.getvalue())
        self.assertNotIn('Unknown command', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())
        alice.respond_to_player.assert_called_once_with('hello')
        alice.receive_gift.assert_called_once_with('joy')
        self.assertEqual(len(alice.gossip), 1)
        world.world_tick.assert_called_once()
        world.save.assert_called_once()

    def test_next_line_waits_for_current_voice_to_finish(self):
        import contextlib
        import io
        world = self.world()
        started = threading.Event()
        release = threading.Event()
        spoken = []
        displayed = threading.Event()
        class Display(io.StringIO):
            def write(self, text):
                result = super().write(text)
                if '\n' in text:
                    displayed.set()
                return result
        output = Display()
        class Engine:
            def setProperty(self, *args): pass
            def say(self, text): spoken.append(text)
            def runAndWait(self):
                started.set()
                if not release.wait(timeout=3):
                    raise RuntimeError('Test did not release speech')
            def stop(self): pass
        def tick():
            world.narrate('Sharp BONKS Krob!')
            world.narrate('Krob replies: hey!')
        with contextlib.redirect_stdout(output), patch.object(mod.sys, 'platform', 'linux'), patch.object(mod.pyttsx3, 'init', return_value=Engine()):
            self.assertTrue(world._start_tts_thread())
            world.tts_enabled = True
            producer = threading.Thread(target=tick, daemon=True)
            producer.start()
            try:
                self.assertTrue(started.wait(timeout=2))
                self.assertTrue(displayed.wait(timeout=2))
                self.assertTrue(producer.is_alive())
                self.assertEqual(output.getvalue().splitlines(), ['Sharp BONKS Krob!'])
                self.assertEqual(spoken, ['Sharp BONKS Krob!'])
            finally:
                release.set()
                producer.join(timeout=3)
                world._stop_tts_thread()
        self.assertFalse(producer.is_alive())
        self.assertEqual(output.getvalue().splitlines(), ['Sharp BONKS Krob!', 'Krob replies: hey!'])
        self.assertEqual(spoken, ['Sharp BONKS Krob!', 'Krob replies: hey!'])

    def test_speech_failure_does_not_trap_narration(self):
        world = self.world()
        class Engine:
            def setProperty(self, *args): pass
            def say(self, text): raise RuntimeError('Speaker failed')
            def stop(self): pass
        with patch.object(mod.sys, 'platform', 'linux'), patch.object(mod.pyttsx3, 'init', return_value=Engine()):
            self.assertTrue(world._start_tts_thread())
            world.tts_enabled = True
            producer = threading.Thread(target=lambda: world.narrate('hello'), daemon=True)
            producer.start()
            producer.join(timeout=2)
            self.assertFalse(producer.is_alive())
            world._stop_tts_thread()
        self.assertEqual(world.tts_error, 'Speaker failed')

    def test_typewriter_outputs_individual_characters(self):
        import contextlib
        import io
        world = self.world()
        world.tts_enabled = True
        world.tts_engine = object()
        writes = []
        class Display(io.StringIO):
            def write(self, text):
                writes.append(text)
                return super().write(text)
        output = Display()
        with contextlib.redirect_stdout(output), patch.object(mod.time, 'sleep') as delay:
            world.narrate('Hello!')
        self.assertEqual(output.getvalue(), 'Hello!\n')
        self.assertEqual([part for part in writes if len(part) == 1 and part != '\n'], list('Hello!'))
        self.assertEqual(delay.call_count, 6)
        delay.assert_called_with(0.035)

    def test_display_waits_for_spoken_word_boundaries(self):
        import contextlib
        import io
        world = self.world()
        world.tts_running = True
        progress = queue.Queue()
        completed = threading.Event()
        word_visible = threading.Event()
        class Display(io.StringIO):
            def write(self, text):
                result = super().write(text)
                if self.getvalue() == 'Sharp':
                    word_visible.set()
                return result
        output = Display()
        with contextlib.redirect_stdout(output):
            producer = threading.Thread(target=lambda: world._type_with_voice('Sharp bonks Krob!', progress, completed), daemon=True)
            producer.start()
            try:
                self.assertEqual(output.getvalue(), '')
                progress.put((0, 5, 1.0))
                self.assertTrue(word_visible.wait(timeout=2))
                self.assertEqual(output.getvalue(), 'Sharp')
                progress.put((6, 11, 1.7))
                progress.put((12, 16, 2.4))
            finally:
                completed.set()
                producer.join(timeout=2)
        self.assertFalse(producer.is_alive())
        self.assertEqual(output.getvalue(), 'Sharp bonks Krob!')

    def test_speech_offsets_map_to_decorated_display(self):
        line = '\U0001f4ac Sharp \u2192 Krob: hello!'
        spoken, indices = mod.LonkWorld._speech_text(line)
        self.assertEqual(spoken, ' Sharp  to  Krob: hello!')
        start = spoken.index('Krob')
        self.assertEqual(line[indices[start]:indices[start + 3] + 1], 'Krob')
        line = '\U00010400 hello'
        spoken, indices = mod.LonkWorld._speech_text(line)
        self.assertEqual(indices[:2], [0, 0])
        self.assertEqual(indices[3], 2)

    def test_ctrl_c_pauses_auto_and_returns_to_commands(self):
        import contextlib
        import io
        from unittest.mock import Mock
        world = self.world()
        world.auto_mode = True
        world.auto_speed = 1
        world.tick = 1
        world.command_parser = mod.CommandParser()
        world.world_tick = Mock(side_effect=KeyboardInterrupt)
        world.save = Mock()
        world.lonks = []
        commands = iter(['help', 'stats', 'quit'])
        def read(prompt):
            self.assertFalse(world.auto_mode)
            world.save.assert_not_called()
            return next(commands)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input', side_effect=read):
            world.interactive_loop()
        self.assertIn('Auto mode paused.', output.getvalue())
        self.assertIn('LEGACY COMMANDS', output.getvalue())
        self.assertIn('WORLD STATS', output.getvalue())
        self.assertNotIn('Interrupted! Saving', output.getvalue())
        world.save.assert_called_once()

    def test_ctrl_c_in_manual_mode_still_saves_and_exits(self):
        import contextlib
        import io
        from unittest.mock import Mock
        world = self.world()
        world.auto_mode = False
        world.save = Mock()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input', side_effect=KeyboardInterrupt):
            world.interactive_loop()
        world.save.assert_called_once()
        self.assertIn('Saved. Goodbye!', output.getvalue())

if __name__ == '__main__':
    unittest.main()
