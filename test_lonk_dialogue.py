"""Behavior checks for compositional, entirely offline dialogue."""
import importlib.util
import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lonk_dialogue import DialogueGenerator


def character(name='Sharp'):
    return SimpleNamespace(name=name, health=80, emotion={'joy': 60, 'anxiety': 20},
                           personality={'curiosity': 75}, territory='The Moss Blanket', items=[])


class GrammarTests(unittest.TestCase):
    def setUp(self):
        self.lonk = character()
        self.dialogue = DialogueGenerator(self.lonk)

    def say(self, text, partner='Player'):
        return self.dialogue.generate_response(text, target=partner)

    def test_feeling_desire_does_not_spread_as_an_instruction(self):
        reply = self.say('I want to feel excited.', 'Brob')
        self.assertNotEqual(reply, 'I want to feel excited.')
        self.assertNotIn('desired_feeling', self.lonk.dialogue_state['Brob'])

    def test_feeling_questions_are_not_instructions(self):
        reply = self.say('What made you feel excited?', 'Brob')
        self.assertNotEqual(reply, 'I want to feel excited.')
        self.assertNotIn('desired_feeling', self.lonk.dialogue_state['Brob'])

    def test_repeated_social_input_uses_other_grounded_information(self):
        self.lonk.items = [{'name': 'Crystal Shard'}, {'name': 'Golden Acorn'}]
        replies = [self.say('I want to feel excited.', 'Brob') for _ in range(8)]
        self.assertTrue(all(reply != 'I want to feel excited.' for reply in replies))
        self.assertTrue(all(a != b for a, b in zip(replies, replies[1:])))
        self.assertGreaterEqual(len(set(replies)), 3)

    def test_new_noun_phrases_and_past_tense_are_preserved(self):
        self.say('I found a turquoise clockwork mushroom')
        self.assertEqual(self.say('what did I find?'), 'You found a turquoise clockwork mushroom.')

    def test_pronouns_colors_and_corrections_follow_the_referent(self):
        self.say('I found a blue rock')
        self.assertEqual(self.say('what color is it?'), 'It is blue.')
        self.say('no it was red')
        self.assertEqual(self.say('what color is it?'), 'It is red.')
        self.assertEqual(self.say('what did I find?'), 'You found the red rock.')
        self.say('I am sad')
        self.say('I lost it')
        self.assertEqual(self.say('what did I lose?'), 'You lost the red rock.')

    def test_negation_is_not_reversed(self):
        self.say("I don't like moss")
        self.assertEqual(self.say('what do I like?'), 'You do not like moss.')
        self.say('I like moss')
        self.assertEqual(self.say('what do I like?'), 'You like moss.')

    def test_memories_are_separate_for_each_partner(self):
        self.say('I found a blue rock', 'Brob')
        self.say('I found a silver spoon', 'Krob')
        self.assertEqual(self.say('what did I find?', 'Brob'), 'You found a blue rock.')
        self.assertEqual(self.say('what did I find?', 'Krob'), 'You found a silver spoon.')
        self.assertNotIn('rock', self.say('what did I find?', 'Player'))

    def test_short_answer_fills_the_question(self):
        question = self.say('I found a blue rock')
        if question.startswith('Where'):
            self.say('by the river')
            response = self.say('where did I find it?')
            self.assertIn('by the river', response)
        else:
            self.say('yesterday')
            response = self.say('when did I find it?')
            self.assertIn('yesterday', response)
        self.assertIn('blue rock', response)

    def test_questions_use_actual_character_state(self):
        self.assertEqual(self.say('where are you?'), 'I am in The Moss Blanket.')
        self.assertEqual(self.say('who are you?'), 'I am Sharp.')
        self.lonk.health = 20
        self.assertIn('injuries', self.say('how are you?'))

    def test_unknown_input_does_not_demand_definitions_or_invent_facts(self):
        reply = self.say('the frabjous zindle has seven dimensions')
        self.assertNotIn('what do you mean', reply.lower())
        self.assertNotIn('I am thinking about', reply)
        self.assertEqual(self.lonk.dialogue_state['Player']['facts'], [])

    def test_negated_words_do_not_trigger_substring_sentiment(self):
        # This engine parses verbs instead of treating "nothing" as a greeting
        # because it happens to contain the letters "hi".
        self.assertNotIn('Hello', self.say('nothing happened'))

    def test_dialogue_needs_no_network_or_model(self):
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            self.say('I found an amber acorn')
            self.assertEqual(self.say('what did I find?'), 'You found an amber acorn.')

    def test_new_definitions_are_learned_without_a_phrase_bank(self):
        self.say('a floob is a tiny purple mushroom')
        self.assertEqual(self.say('what is a floob?'), 'A floob is a tiny purple mushroom.')
        self.assertNotIn('purple', self.say('what is a floob?', partner='Brob'))

    def test_followup_why_does_not_repeat_the_same_question(self):
        first = self.say('I found a blue rock')
        reply = self.say('why?')
        self.assertNotEqual(first, reply)
        self.assertIn('blue rock', reply)

    def test_taught_swear_is_reused_immediately_in_next_conversation(self):
        self.say('fuck')
        with patch('lonk_dialogue.random.random', return_value=1), patch('lonk_dialogue.random.choice', side_effect=lambda options: options[0]):
            self.assertIn('fuck', self.say(None, 'Brob').lower())
            # After the first guaranteed try, normal variation resumes.
            self.assertNotIn('fuck', self.say(None, 'Krob').lower())

    def test_regular_invented_words_use_the_same_learning_path(self):
        self.say('floob')
        with patch('lonk_dialogue.random.random', return_value=0), patch('lonk_dialogue.random.choice', side_effect=lambda options: options[0]):
            for _ in range(3):
                self.say(None, 'Brob')
            self.assertIn('floob', self.say(None, 'Brob').lower())

    def test_unlearned_swears_do_not_appear(self):
        with patch('lonk_dialogue.random.random', return_value=0):
            for _ in range(8):
                self.assertNotIn('fuck', self.say(None).lower())

    def test_wordplay_does_not_modify_factual_recall(self):
        self.say('fuck')
        self.say('I found a blue rock')
        with patch('lonk_dialogue.random.random', return_value=0):
            self.assertEqual(self.say('what did I find?'), 'You found a blue rock.')

    def test_lexical_experiments_spread_by_hearing_other_lonks(self):
        other = DialogueGenerator(character('Brob'))
        with patch('lonk_dialogue.random.random', return_value=0), patch('lonk_dialogue.random.choice', side_effect=lambda options: options[0]):
            utterance = self.say('fuck')
            other.generate_response(utterance, target='Sharp')
            self.assertTrue(other.generate_response(None, target='Krob').startswith('I feel fuck.'))

    def test_single_taught_word_is_tried_instead_of_rejected(self):
        with patch('lonk_dialogue.random.choice', side_effect=lambda options: options[0]):
            self.assertEqual(self.say('fuck'), 'I feel fuck.')
            engine = DialogueGenerator(character())
            self.assertEqual(engine.generate_response('floob'), 'I feel floob.')

    def test_mood_question_allows_added_words_and_punctuation(self):
        with patch('lonk_dialogue.random.random', return_value=1):
            self.assertEqual(self.say('how are you fuck'), 'I feel fuck curious.')
            self.assertEqual(self.say('hey, how are you, fuck?'), 'I feel curious.')
        self.assertIn('fuck', self.lonk.wordplay_state['words'])

    def test_all_place_questions_can_use_a_just_taught_word(self):
        for place in ('The Loud Bush', 'The Unreasonable Clearing', 'The Shiny Pit'):
            engine = DialogueGenerator(character())
            engine.generate_response('fuck', target='Player')
            with patch('lonk_dialogue.random.random', return_value=1):
                reply = engine.adapt_spoken_line('What do you think about ' + place + '?')
            self.assertEqual(reply, 'What the fuck do you think about ' + place + '?')

    def test_words_already_in_the_sentence_are_not_doubled(self):
        self.say('reassurance')
        with patch('lonk_dialogue.random.random', return_value=0):
            self.assertEqual(self.dialogue.adapt_spoken_line('I need reassurance.'), 'I need reassurance.')

    def test_expressive_grammar_preserves_question_understanding(self):
        self.say('I found a blue rock')
        self.assertEqual(self.say('What the fuck did I find?'), 'You found a blue rock.')

    def test_expressive_interjections_preserve_remembered_facts(self):
        self.say('Fuck. I found a blue rock')
        self.assertEqual(self.say('what did I find?'), 'You found a blue rock.')

    def test_ordinary_dialogue_words_do_not_become_expletives(self):
        for line in ('I need reassurance', 'I need something to keep',
                     'What do you think about The Screaming Meadow?'):
            self.say(line, 'Brob')
        self.assertEqual(self.lonk.wordplay_state['expressive'], {})
        with patch('lonk_dialogue.random.random', return_value=0):
            self.assertEqual(self.dialogue.adapt_spoken_line('I feel calm.'), 'I feel calm.')

    def test_old_polluted_lexicon_preserves_explicit_user_lessons_only(self):
        self.lonk.wordplay_state = {'words': {'fuck': 3, 'keep': 20, 'reassurance': 20}, 'pending_word': 'keep'}
        self.lonk.memory = {'player_words': {'fuck', 'how', 'are', 'you'},
            'player_interactions': [{'message': 'fuck'}, {'message': 'how are you'}]}
        self.say(None)
        self.assertEqual(set(self.lonk.wordplay_state['expressive']), {'fuck'})
        self.assertNotEqual(self.lonk.wordplay_state.get('pending_word'), 'keep')

    def test_place_question_uses_its_description_not_a_noun_fragment(self):
        self.lonk.world = SimpleNamespace(lonks=[], config={'territories': {
            'The Loud Bush': {'vibe': 'rustles aggressively for no reason'},
            'The Screaming Meadow': {'vibe': 'the grass yells compliments'},
            'The Unreasonable Clearing': {'vibe': 'geometry makes no sense here'}}})
        for place in self.lonk.world.config['territories']:
            reply = self.say('What do you think about ' + place + '?', 'Brob')
            self.assertIn(place, reply)
            self.assertNotIn('I am thinking about', reply)
            self.assertNotIn('What the', reply)
        self.assertEqual(self.lonk.wordplay_state['expressive'], {})

    def test_unprompted_speech_does_not_cycle_generic_place_questions(self):
        for _ in range(12):
            reply = self.say(None, 'Brob')
            self.assertNotIn('What do you think about', reply)
            self.assertNotIn('I am thinking about', reply)

    def test_reassurance_request_gets_support_not_an_interrogation(self):
        reply = self.say('I need reassurance', 'Brob')
        self.assertIn('with you', reply)
        self.assertNotIn('Why', reply)

    def test_world_peers_copy_expressive_words_with_provenance(self):
        other_lonk = character('Brob')
        other = DialogueGenerator(other_lonk)
        world = SimpleNamespace(lonks=[self.lonk, other_lonk], config={})
        self.lonk.world = other_lonk.world = world
        self.say('fuck')
        other.generate_response('What the fuck do you think about The Loud Bush?', target='Sharp')
        self.assertIn('fuck', other_lonk.wordplay_state['expressive'])
        other.generate_response('What the keep do you think about The Loud Bush?', target='Sharp')
        self.assertNotIn('keep', other_lonk.wordplay_state['expressive'])

    def test_also_and_still_preserve_the_clause_and_topic(self):
        self.say('fuck')
        reply = self.say('I also feel fuck')
        self.assertIn('feel fuck', reply.lower())
        self.assertNotIn('Moss Blanket', reply)
        self.assertEqual(self.say('what do I feel?'), 'You feel fuck.')
        self.say('I still like moss')
        self.assertEqual(self.say('what do I like?'), 'You like moss.')

    def test_permission_is_not_treated_as_an_unrelated_mood(self):
        reply = self.say('you can want fuck')
        self.assertIn('I can want fuck', reply)
        self.assertNotIn('Moss Blanket', reply)

    def test_short_why_refers_to_the_actual_previous_statement(self):
        self.lonk.location_reason = {'kind': 'wandering', 'place': 'The Moss Blanket'}
        self.assertEqual(self.say('where are you?'), 'I am in The Moss Blanket.')
        self.assertEqual(self.say('why?'), 'I wandered into The Moss Blanket.')

    def test_location_question_does_not_answer_with_an_emotion(self):
        self.lonk.location_reason = {'kind': 'wandering', 'place': 'The Moss Blanket'}
        reply = self.say('why are you in the moss blanket?')
        self.assertEqual(reply, 'I wandered into The Moss Blanket.')
        self.assertEqual(self.say('why are you in The Big Rock?'), 'I am in The Moss Blanket.')

    def test_feeling_request_is_acknowledged_as_a_request(self):
        reply = self.say("don't do that feel fucking love and fucking peace")
        self.assertEqual(reply, 'I want to feel love and peace.')
        self.assertEqual(self.lonk.dialogue_state['Player']['desired_feeling'], ['love', 'peace'])
        self.assertIn('fucking', self.lonk.wordplay_state['expressive'])

    def test_unsupported_input_is_learned_as_language_not_as_a_factual_claim(self):
        reply = self.say('please untangle the zindle paradox backwards')
        self.assertIn('untangle the zindle paradox', reply)
        self.assertNotIn('cannot follow', reply)
        self.assertNotIn('Moss Blanket', reply)
        self.assertEqual(self.lonk.dialogue_state['Player']['facts'], [])

    def test_acknowledgements_are_not_mistaken_for_mood_questions(self):
        self.assertIn('okay', self.say('okay bro fuck').lower())

    def test_nonsense_chant_is_learned_and_reused_whole(self):
        chant = 'Wubba Lubba Dub Dub'
        reply = self.say(chant + '!')
        self.assertIn(chant, reply)
        self.assertNotIn('cannot follow', reply)
        self.assertIn(chant.lower(), self.lonk.wordplay_state['phrases'])
        with patch('lonk_dialogue.random.random', return_value=1):
            self.assertIn(chant, self.say(None, 'Brob'))

    def test_long_messages_prioritize_short_repeated_chunks(self):
        text = ('Gather your rocks together, Brob. Put every shiny rock in the moss basket. '
                'Gather your rocks together. Bring the basket to the clearing when it stops raining. '
                'Gather your rocks together.')
        reply = self.say(text)
        self.assertIn('Gather your rocks together', reply)
        self.assertNotIn('cannot follow', reply)
        phrases = self.lonk.wordplay_state['phrases']
        self.assertIn('gather your rocks together', phrases)
        self.assertTrue(all(len(key.split()) <= 8 and len(key) <= 100 for key in phrases))
        self.assertEqual(self.lonk.dialogue_state['Player']['facts'], [])

    def test_sayings_spread_between_lonks_without_learning_factory_phrases(self):
        other_lonk = character('Brob')
        other = DialogueGenerator(other_lonk)
        world = SimpleNamespace(lonks=[self.lonk, other_lonk], config={})
        self.lonk.world = other_lonk.world = world
        first = self.say('Wubba Lubba Dub Dub!')
        other.generate_response(first, target='Sharp')
        self.assertIn('wubba lubba dub dub', other_lonk.wordplay_state['phrases'])
        self.assertNotIn('i feel curious', other_lonk.wordplay_state['phrases'])

    def test_phrase_prefix_does_not_hide_the_actual_statement(self):
        self.say('Wubba Lubba Dub Dub!')
        reply = self.say('Wubba Lubba Dub Dub! I found a blue rock', 'Player')
        self.assertIn('blue rock', reply)
        self.assertEqual(self.say('what did I find?'), 'You found a blue rock.')

    def test_words_taught_before_upgrade_are_available(self):
        self.lonk.memory = {'player_words': {'fuck!'}}
        with patch('lonk_dialogue.random.random', return_value=0), patch('lonk_dialogue.random.choice', side_effect=lambda options: options[0]):
            self.assertTrue(self.say(None).startswith('I feel fuck.'))


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('dialogue_simulator',
            'dynamiclonk-py-v13-lonks-finally-have-ears-say-command-fixed.py')
        cls.sim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.sim)

    def test_player_path_does_not_append_random_words(self):
        lonk = self.sim.Lonk(name='Sharp', _loading=True)
        lonk.respond_to_player('I found a violet glass snail')
        self.assertEqual(lonk.respond_to_player('what did I find?'), 'You found a violet glass snail.')

    def test_continuation_responds_to_actual_last_turn(self):
        lonk = self.sim.Lonk(name='Sharp', _loading=True)
        other = self.sim.Lonk(name='Brob', _loading=True)
        conversation = self.sim.Conversation('Sharp', 'Brob', topic='food')
        conversation.add_turn('Brob', 'I found a blue rock', {'joy': 50}, 1)
        lonk.active_conversations['Brob'] = conversation
        with patch.object(lonk, '_should_continue_dialogue', return_value=True):
            reply = lonk.continue_conversation(other, 2)
        self.assertIn('blue rock', reply)
        self.assertNotIn('food', reply)
        self.assertFalse(reply.startswith('Sharp:'))
        self.assertEqual(conversation.turns[-1].message, reply)

    def test_context_survives_save_load_and_old_saves(self):
        lonk = self.sim.Lonk(name='Sharp', _loading=True)
        lonk.respond_to_player('I found a blue rock')
        saved = lonk.to_dict()
        json.dumps(saved['dialogue_state'])
        restored = self.sim.Lonk.from_dict(saved)
        self.assertEqual(restored.respond_to_player('what did I find?'), 'You found a blue rock.')
        saved.pop('dialogue_state')
        restored = self.sim.Lonk.from_dict(saved)
        self.assertTrue(restored.respond_to_player('hello'))

    def test_wordplay_vocabulary_and_cooldown_survive_save_load(self):
        lonk = self.sim.Lonk(name='Sharp', _loading=True)
        lonk.respond_to_player('fuck')
        with patch('lonk_dialogue.random.random', return_value=0):
            lonk.dialogue_generator._wordplay('I need reassurance.', lonk.wordplay_state)
        saved = lonk.to_dict()
        json.dumps(saved['wordplay_state'])
        restored = self.sim.Lonk.from_dict(saved)
        self.assertEqual(restored.wordplay_state, lonk.wordplay_state)
        self.assertIn('fuck', restored.wordplay_state['words'])

    def test_location_reasons_survive_save_load(self):
        lonk = self.sim.Lonk(name='Ship', _loading=True)
        with contextlib.redirect_stdout(io.StringIO()):
            lonk.wander()
            restored = self.sim.Lonk.from_dict(lonk.to_dict())
        self.assertEqual(restored.location_reason, lonk.location_reason)
        self.assertEqual(restored.respond_to_player('why are you in ' + restored.territory),
                         'I wandered into ' + restored.territory + '.')

    def test_learned_sayings_survive_save_load(self):
        lonk = self.sim.Lonk(name='Ship', _loading=True)
        lonk.respond_to_player('Wubba Lubba Dub Dub!')
        saved = lonk.to_dict()
        json.dumps(saved['wordplay_state'])
        with contextlib.redirect_stdout(io.StringIO()):
            restored = self.sim.Lonk.from_dict(saved)
        self.assertIn('wubba lubba dub dub', restored.wordplay_state['phrases'])


if __name__ == '__main__':
    unittest.main()
