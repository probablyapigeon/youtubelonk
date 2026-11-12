# ============================================================
# DYNAMIC LONK CIVILIZATION SIMULATOR
# Requires: numpy (only external dependency)
# Features: Neural learning, emotional dynamics, composable actions,
#           factions, religion, trading, gossip, memory, lifecycle,
#           weight-space programming (direct weight editing),
#           TTS (optional), Auto mode
# ============================================================

import random
import math
import time
import os
import json
import sys
import re
from collections import deque
import numpy as np
import threading
import queue
import uuid
import copy
from contextlib import redirect_stdout, contextmanager, ExitStack
from lonk_semantics import SemanticTrace
from lonk_society import Civilization
from lonk_dialogue import DialogueGenerator
from lonk_visuals import ColorOutput, enable_colors, event_color, RESET
from lonk_live import TerminalWorldView
from lonk_quotes import QuoteLibrary
from lonk_youtube import YouTubeBridge


class _TickSpeechOutput:
    """Send complete printed tick lines through the paced narrator."""
    def __init__(self, world, output):
        self.world = world
        self.output = output
        self.pending = ''

    def write(self, text):
        self.pending += text
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            with redirect_stdout(self.output):
                if line.strip():
                    self.world.narrate(line)
                else:
                    print(line, flush=True)
        return len(text)

    def flush(self):
        self.output.flush()

    def finish(self):
        if self.pending:
            line, self.pending = self.pending, ''
            with redirect_stdout(self.output):
                self.world.narrate(line)

# Try to import pyttsx3 for TTS (optional)
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ============================================================
# LONK INNER MONOLOGUE SYSTEM
# Generates autonomous inner thoughts based on emotional state
# ============================================================

class LonkInnerMonologue:
    """Generates inner thoughts and autonomous monologue for Lonks"""
    
    def __init__(self, lonk_name):
        self.lonk_name = lonk_name
        self.inner_thoughts = []
        
        # Thought templates based on emotional/psychological state
        self.thought_patterns = {
            "anxious": [
                "Is someone watching me? I feel exposed...",
                "Something doesn't feel right. I should be careful.",
                "Why am I so nervous? What's wrong?",
                "I can't shake this feeling of dread.",
                "What if something bad happens?",
            ],
            "joyful": [
                "Everything feels possible right now!",
                "This is wonderful. I love this moment.",
                "I'm alive and everything is beautiful.",
                "Good things are happening. I can feel it.",
                "Pure happiness. Nothing else matters.",
            ],
            "contemplative": [
                "What does it all mean? Why are we here?",
                "I've been thinking about that encounter...",
                "Reality is stranger than I expected.",
                "Maybe I was wrong about that Lonk.",
                "I need to understand this better.",
            ],
            "restless": [
                "I want to move, to do something.",
                "Staying still feels wrong. Energy building.",
                "There's potential I haven't used yet.",
                "I need a change. Something's got to give.",
                "Movement. Action. That's what I crave.",
            ],
            "sad": [
                "Everything feels heavy right now.",
                "I miss the way things used to be.",
                "Why does it hurt so much?",
                "I don't know if I can keep going.",
                "Will this emptiness ever pass?",
            ],
            "aggressive": [
                "I want to fight. To prove myself.",
                "Someone will pay for this disrespect.",
                "Power. Dominance. That's all that matters.",
                "I need to show them what I'm capable of.",
                "This anger... I can't contain it.",
            ],
            "curious": [
                "I wonder about that strange thing I saw.",
                "What if I tried something different?",
                "There's so much I don't understand yet.",
                "That pattern... what does it mean?",
                "I should explore this further.",
            ],
            "dreamy": [
                "Reality feels softer, more fluid...",
                "I'm floating between worlds.",
                "Is this real or a dream?",
                "Time moves differently here.",
                "The boundaries between things are blurring.",
            ],
        }
    
    def generate_thought(self, lonk):
        """Generate an inner thought based on Lonk's current state"""
        # Determine emotional state from emotion dictionary
        emotion_state = self._determine_state(lonk)
        
        if emotion_state not in self.thought_patterns:
            emotion_state = "contemplative"
        
        patterns = self.thought_patterns[emotion_state]
        thought = random.choice(patterns)
        
        # Record the thought
        thought_record = {
            "thought": thought,
            "emotional_state": emotion_state,
            "tick": getattr(lonk.world, 'tick', 0) if lonk.world else 0,
            "health": lonk.health,
            "joy": lonk.emotion.get("joy", 50),
            "anxiety": lonk.emotion.get("anxiety", 50),
        }
        self.inner_thoughts.append(thought_record)
        
        return thought
    
    def _determine_state(self, lonk):
        """Determine emotional state from Lonk's emotion values"""
        anxiety = lonk.emotion.get("anxiety", 50)
        joy = lonk.emotion.get("joy", 50)
        courage = lonk.emotion.get("courage", 50)
        aggression = lonk.personality.get("aggression", 50)
        curiosity = lonk.personality.get("curiosity", 50)
        
        # Higher anxiety = anxious or dreamy
        if anxiety > 70:
            if joy > 60:
                return "dreamy"
            return "anxious"
        
        # Higher joy = joyful
        if joy > 70:
            return "joyful"
        
        # Low joy, low anxiety = sad or contemplative
        if joy < 30:
            if anxiety < 30:
                return "sad"
            return "contemplative"
        
        # High aggression + low joy = aggressive
        if aggression > 70 and joy < 40:
            return "aggressive"
        
        # High curiosity = curious
        if curiosity > 70:
            return "curious"
        
        # Health-based restlessness
        if lonk.health > 80 and courage > 60:
            return "restless"
        
        return "contemplative"
    
    def get_recent_thoughts(self, count=3):
        """Get the last N thoughts"""
        return self.inner_thoughts[-count:] if self.inner_thoughts else []
    
    def to_dict(self):
        """Serialize for save/load"""
        return {
            "lonk_name": self.lonk_name,
            "inner_thoughts": self.inner_thoughts[-100:]  # Keep last 100
        }
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize from save/load"""
        obj = cls(data.get("lonk_name", "Unknown"))
        obj.inner_thoughts = data.get("inner_thoughts", [])
        return obj

# ============================================================
# PHASE 1: INTERACTION SYSTEMS (v14)
# Conversation, DialogueGenerator, and CommandParser classes
# ============================================================

class Turn:
    """Single message exchange in a conversation"""
    
    def __init__(self, speaker_name, message, emotion_state, timestamp):
        self.speaker_name = speaker_name
        self.message = message
        self.emotion_state = emotion_state.copy() if emotion_state else {}
        self.timestamp = timestamp
    
    def to_dict(self):
        return {
            "speaker_name": self.speaker_name,
            "message": self.message,
            "emotion_state": self.emotion_state,
            "timestamp": self.timestamp,
        }
    
    @staticmethod
    def from_dict(data):
        return Turn(
            data["speaker_name"],
            data["message"],
            data.get("emotion_state", {}),
            data["timestamp"]
        )
    
    def __repr__(self):
        return f"Turn({self.speaker_name}: '{self.message[:30]}...' @tick {self.timestamp})"


class Conversation:
    """Multi-turn dialogue between two Lonks with persistence"""
    
    def __init__(self, participant1_name, participant2_name, topic=None, initiated_tick=0):
        self.participants = {participant1_name, participant2_name}
        self.participant_names = (participant1_name, participant2_name)
        self.turns = []
        self.topic = topic or "general"
        self.context = ""
        self.initiated_tick = initiated_tick
        self.last_activity_tick = initiated_tick
    
    def add_turn(self, speaker_name, message, emotion_state, timestamp):
        if speaker_name not in self.participants:
            raise ValueError(f"{speaker_name} not in conversation")
        turn = Turn(speaker_name, message, emotion_state, timestamp)
        self.turns.append(turn)
        self.last_activity_tick = timestamp
        return turn
    
    def is_stale(self, current_tick, timeout=25):
        return (current_tick - self.last_activity_tick) > timeout
    
    def is_concluded(self):
        if not self.turns:
            return False
        last_turn = self.turns[-1]
        last_emotion = last_turn.emotion_state
        xenolethargic_level = last_emotion.get("xenolethargic", 0)
        joy = last_emotion.get("joy", 0)
        return xenolethargic_level > 70 or joy < 20
    
    def get_conversation_memory(self):
        if not self.turns:
            return ""
        summary_lines = [f"Talked with {', '.join(p for p in self.participants)}: {self.topic}"]
        for turn in self.turns[-5:]:
            summary_lines.append(f"  {turn.speaker_name}: {turn.message[:60]}")
        return "\n".join(summary_lines)
    
    def to_dict(self):
        return {
            "participant_names": list(self.participant_names),
            "turns": [t.to_dict() for t in self.turns],
            "topic": self.topic,
            "context": self.context,
            "initiated_tick": self.initiated_tick,
            "last_activity_tick": self.last_activity_tick,
        }
    
    @staticmethod
    def from_dict(data):
        names = data["participant_names"]
        conv = Conversation(names[0], names[1], data.get("topic"), data["initiated_tick"])
        conv.last_activity_tick = data.get("last_activity_tick", data["initiated_tick"])
        conv.context = data.get("context", "")
        conv.turns = [Turn.from_dict(t) for t in data.get("turns", [])]
        return conv
    
    def __repr__(self):
        return f"Conversation({', '.join(self.participant_names)}: {self.topic}, {len(self.turns)} turns)"


class CommandParser:
    """Parses player commands with flexible syntax"""
    
    def __init__(self):
        self.COMMANDS = {
            "say": "Talk to a Lonk",
            "interact": "Perform action toward a Lonk",
            "listen": "Hear a Lonk's memory/thoughts",
            "observe": "Check a Lonk's emotional state",
            "gossip": "Seed a rumor in the world",
            "gift": "Give emotions, care, health, or a physical item",
            "quotes": "Load a local quote file, teach NAME, or turn automatic quote learning on/off",
            "youtube": "Connect/reconnect YouTube chat, setup, status, disconnect, or pump",
        }
        self.COMMANDS.update(Civilization.COMMANDS)
    
    def parse(self, input_str):
        if not input_str or not input_str.strip():
            return (None, {}, "Empty input")
        input_str = input_str.strip()
        if input_str.startswith("/"):
            return self._parse_slash(input_str)
        else:
            return self._parse_legacy(input_str)
    
    def _parse_slash(self, input_str):
        input_str = input_str[1:].strip()
        parts = input_str.split(None, 1)
        command = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        if command not in self.COMMANDS:
            return (None, {}, f"Unknown command: /{command}")
        args, error = self._parse_args(command, rest)
        return (command, args, error)
    
    def _parse_legacy(self, input_str):
        parts = input_str.split(None, 1)
        command = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        if command not in self.COMMANDS:
            return (None, {}, f"Unknown command: {command}")
        args, error = self._parse_args(command, rest)
        return (command, args, error)
    
    def _parse_args(self, command, rest):
        rest = rest.strip()
        if command in ('quotes', 'youtube'):
            return ({'raw': rest}, None)
        if command in Civilization.COMMANDS:
            return ({'raw': rest}, None)
        if command == "say":
            parts = rest.split(None, 1)
            if not parts:
                return ({}, "Usage: /say <name> [message]")
            target = parts[0]
            message = parts[1] if len(parts) > 1 else ""
            message = self._unquote(message)
            return ({"target": target, "message": message}, None)
        elif command == "interact":
            parts = rest.split(None, 1)
            if not parts:
                return ({}, "Usage: /interact <name> [action]")
            target = parts[0]
            action = parts[1] if len(parts) > 1 else "greet"
            return ({"target": target, "action": action}, None)
        elif command == "listen":
            if not rest:
                return ({}, "Usage: /listen <name>")
            target = rest.split()[0]
            return ({"target": target}, None)
        elif command == "observe":
            if not rest:
                return ({}, "Usage: /observe <name>")
            target = rest.split()[0]
            return ({"target": target}, None)
        elif command == "gossip":
            if not rest:
                return ({}, "Usage: /gossip <rumor>")
            rumor = self._unquote(rest)
            return ({"rumor": rumor}, None)
        elif command == "gift":
            parts = rest.split(None, 1)
            if not parts:
                return ({}, "Usage: /gift <name> [emotion]")
            target = parts[0]
            emotion = parts[1] if len(parts) > 1 else "joy"
            return ({"target": target, "emotion": emotion}, None)
        else:
            return ({}, f"Unknown command: {command}")
    
    def _unquote(self, text):
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            return text[1:-1]
        return text
    
    def help(self):
        lines = ["\n" + "="*60, "COMMANDS", "="*60]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"  /{cmd:<10} - {desc}")
        lines.extend([
            "", "EXAMPLES:",
            "  /say Alice hello world",
            "  /say Alice \"hello there\"",
            "  /interact Bob greet",
            "  /observe Alice",
            "  /listen Bob",
            "  /gossip \"Alice is really nice\"",
            "  /gift Alice joy",
            "", "LEGACY SYNTAX (also supported):",
            "  say alice hello world",
            "  interact bob greet",
            "  observe alice",
            "", "="*60,
        ])
        return "\n".join(lines)

# ============================================================
# CONFIGURATION
# ============================================================

# Learning parameters
LEARNING_RATE = 0.01
REWARD_V2 = True        # balanced reward (health/social/knowledge); False = original
TD_GAMMA = 0.9          # discount on future value
ENTROPY_BONUS = 0.01    # keeps exploration alive
CRITIC_WEIGHT = 0.5
# Hard-coded instincts (need overrides) fade as the net gains experience
INSTINCT_FADE_UPDATES = 3000
MIN_INSTINCT = 0.4
GAMMA = 0.99  # Discount factor
BATCH_SIZE = 32
MEMORY_CAPACITY = 500
HIDDEN_SIZE = 16
INPUT_SIZE = 32
OUTPUT_SIZE = 6  # Must match len(Lonk.ACTIONS)

# World parameters
MAX_HEALTH = 100
FIGHT_DAMAGE = 5
MAX_VERBS = 20  # Cap verb inventory per agent
MAX_GOSSIP = 20
STARTING_POPULATION = 5

# Toggles
TOGGLES = {
    "violence": True,
    "shinywars": True,
    "dreams": True,
    "religion": True,
    "trading": True,
    "gossip": True,
    "weight_programming": True
}

# Weight-Space Programming settings (homage to MIT CSAIL's Weight-Space
# Programming, Nov 2026: an external editor reads and rewrites a model's
# weights directly, with no gradient descent and no training data)
WP_INTERVAL = 10          # programmer edits the chosen brain every N ticks
WP_REPORT_INTERVAL = 50   # automatic chosen-vs-others report every N ticks
WP_HISTORY = 200          # reward history window kept per Lonk
WP_MAX_PATCH = 60         # safety cap: max weight patches per edit

# ============================================================
# AUTONOMOUS EPISTEMOLOGY (v11)
# Lonks write their own axioms, test them against reality, drift
# their own values (will), and undergo paradigm shifts when their
# worldview collapses. No human-programmed objective drives the
# will - surprise itself pulls at it (intrinsic motivation).
# ============================================================
EPISTEMOLOGY_ON = True    # master switch
EPI_AXIOM_INTERVAL = 15  # every N ticks, one lonk writes a new axiom
EPI_WILL_STRENGTH = 0.35 # chance an action is drawn from will, not the net
EPI_MAX_AXIOMS = 8       # live axioms per lonk (weakest get overwritten)
EPI_MIN_PREDICTIONS = 5  # predictions before an axiom may be judged
EPI_CANON_ACCURACY = 0.55  # accuracy needed to canonize (plus skepticism)
EPI_SHIFT_FALSIFIED = 3   # recent falsifications that trigger a paradigm shift
EPI_SHIFT_COOLDOWN = 75   # min ticks between a lonk's paradigm shifts

# Violence tuning. These replace the old hardcoded attack dice; lower
# values mean longer lives and cleaner weight-space programming
# measurements. Set TOGGLES["violence"] to False to zero them all out.
VIOLENCE = {
    "random_attack": 0.01,
    "discomfort_attack": 0.05,
    "items_attack": 0.02,
    "knowledge_attack": 0.0,
    "territory_attack": 0.05,
    "random_combat": 0.005,
}


def _v(key):
    """Look up a violence probability; 0.0 when the violence toggle is off."""
    if not TOGGLES.get("violence", True):
        return 0.0
    return VIOLENCE.get(key, 0.0)

# ============================================================
# XEMBRA EMOTIONS (50+ rich emotional states)
# ============================================================

XEMBRA_EMOTIONS = {
    # Core emotions
    "peaceful": {"valence": 0.8, "arousal": 0.2, "dominance": 0.5},
    "zen": {"valence": 0.7, "arousal": 0.1, "dominance": 0.4},
    "happy": {"valence": 0.9, "arousal": 0.6, "dominance": 0.5},
    "joyful": {"valence": 1.0, "arousal": 0.7, "dominance": 0.4},
    "excited": {"valence": 0.8, "arousal": 0.9, "dominance": 0.6},
    "sad": {"valence": 0.2, "arousal": 0.3, "dominance": 0.3},
    "angry": {"valence": 0.3, "arousal": 0.9, "dominance": 0.8},
    "afraid": {"valence": 0.1, "arousal": 0.8, "dominance": 0.2},
    "calm": {"valence": 0.7, "arousal": 0.2, "dominance": 0.5},
    "anxious": {"valence": 0.3, "arousal": 0.7, "dominance": 0.3},

    # Xembra-specific emotions (alien, cosmic, dreamlike)
    "xenic": {"valence": 0.6, "arousal": 0.5, "dominance": 0.4},
    "xenowarm": {"valence": 0.8, "arousal": 0.4, "dominance": 0.3},
    "xenofear": {"valence": 0.2, "arousal": 0.8, "dominance": 0.2},
    "xenoshy": {"valence": 0.4, "arousal": 0.6, "dominance": 0.2},
    "xenophilous": {"valence": 0.7, "arousal": 0.5, "dominance": 0.4},
    "xenoanger": {"valence": 0.3, "arousal": 0.8, "dominance": 0.7},
    "xenojoy": {"valence": 0.9, "arousal": 0.6, "dominance": 0.4},
    "xenolove": {"valence": 0.95, "arousal": 0.5, "dominance": 0.3},
    "xenolethargic": {"valence": 0.4, "arousal": 0.1, "dominance": 0.2},

    # Dream states
    "floating": {"valence": 0.7, "arousal": 0.3, "dominance": 0.3},
    "opaline": {"valence": 0.6, "arousal": 0.4, "dominance": 0.4},
    "iridescent calm": {"valence": 0.8, "arousal": 0.2, "dominance": 0.4},
    "soft stillness": {"valence": 0.7, "arousal": 0.1, "dominance": 0.3},
    "holy-soft awe": {"valence": 0.8, "arousal": 0.4, "dominance": 0.3},
    "nectar-soft": {"valence": 0.9, "arousal": 0.3, "dominance": 0.2},
    "honey-warm": {"valence": 0.85, "arousal": 0.3, "dominance": 0.3},
    "numinous": {"valence": 0.8, "arousal": 0.5, "dominance": 0.4},
    "astral": {"valence": 0.6, "arousal": 0.4, "dominance": 0.5},
    "curling inward": {"valence": 0.3, "arousal": 0.5, "dominance": 0.2},
    "pulling back": {"valence": 0.4, "arousal": 0.6, "dominance": 0.3},
    "in a zen state": {"valence": 0.75, "arousal": 0.2, "dominance": 0.4},
    "slow sweetness": {"valence": 0.85, "arousal": 0.3, "dominance": 0.3},

    # Combat emotions
    "combat energy": {"valence": 0.5, "arousal": 0.9, "dominance": 0.8},
    "with combat energy": {"valence": 0.5, "arousal": 0.9, "dominance": 0.8},
    "violent": {"valence": 0.2, "arousal": 0.9, "dominance": 0.9},
    "furious": {"valence": 0.1, "arousal": 1.0, "dominance": 0.9},
    "enraged": {"valence": 0.0, "arousal": 1.0, "dominance": 1.0},
}

# ============================================================
# FACTIONS
# ============================================================

FACTIONS = [
    {"name": "Mushroom Union", "description": "Peaceful foragers who believe in the mycelial network",
     "bonus": {"wisdom": +10, "loyalty": +5}},
    {"name": "Bonk Battalion", "description": "Warrior Lonks who solve problems with violence",
     "bonus": {"aggression": +15, "courage": +10}},
    {"name": "Shiny Collectors", "description": "Obsessed with collecting shiny objects",
     "bonus": {"curiosity": +15, "joy": +5}},
    {"name": "Dreamweavers", "description": "Mystical Lonks who commune with the void",
     "bonus": {"wisdom": +10, "anxiety": -5}},
    {"name": "Chaos Choir", "description": "Anarchic Lonks who love noise and disorder",
     "bonus": {"playfulness": +15, "anxiety": +5}},
]

# ============================================================
# RELIGIONS
# ============================================================

RELIGIONS = {
    "Mushroom Union": {
        "name": "Mycelial Network",
        "description": "Worship of the cosmic mycelium that connects all things",
        "ritual": "consumes sacred objects to join the cosmic mycelium",
        "ritual_description": "consumes sacred objects to join the cosmic mycelium",
        "sacred_items": ["Glowing Cap", "Sacred Spore", "Moss Blanket"],
        "deity": "The Great Mycelium"
    },
    "Bonk Battalion": {
        "name": "Order of the Sacred Bonk",
        "description": "Belief that bonking is a sacred act of devotion",
        "ritual": "bonks sacred objects (and each other) to prove devotion",
        "ritual_description": "bonks sacred objects (and each other) to prove devotion",
        "sacred_items": ["Bonk Hammer", "Sacred Anvil", "Warrior's Shield"],
        "deity": "The Eternal Bonk"
    },
    "Shiny Collectors": {
        "name": "Church of the Shiny",
        "description": "Worship of shiny objects as divine gifts",
        "ritual": "polishes shiny objects to honor their divine nature",
        "ritual_description": "polishes shiny objects to honor their divine nature",
        "sacred_items": ["Golden Acorn", "Crystal Shard", "Pocket Void"],
        "deity": "The Shining One"
    },
    "Dreamweavers": {
        "name": "Cult of the Void",
        "description": "Communion with the cosmic void and dream realms",
        "ritual": "enters trance to commune with the void",
        "ritual_description": "enters trance to commune with the void",
        "sacred_items": ["Void Pearl", "Dream Stone", "Haunted Leaf"],
        "deity": "The Dreaming Void"
    },
    "Chaos Choir": {
        "name": "Church of the Eternal Scream",
        "description": "Worship through noise, chaos, and screaming at bushes",
        "ritual": "screams at the sacred bush to summon chaos",
        "ritual_description": "screams at the sacred bush to summon chaos",
        "sacred_items": ["Screaming Stone", "Chaos Bell", "Noisy Rock"],
        "deity": "The Screaming Chaos"
    },
}

# ============================================================
# TERRITORIES
# ============================================================

TERRITORIES = [
    {"name": "The Moss Blanket", "description": "soft, damp, emotionally supportive",
     "faction_bonus": {"Mushroom Union": 10, "Dreamweavers": 5}},
    {"name": "The Shiny Pit", "description": "glimmers ominously, hums in F#",
     "faction_bonus": {"Shiny Collectors": 15, "Chaos Choir": 5}},
    {"name": "The Big Rock", "description": "immovable, judgmental, slightly warm",
     "faction_bonus": {"Bonk Battalion": 10}},
    {"name": "The Loud Bush", "description": "rustles aggressively for no reason",
     "faction_bonus": {"Chaos Choir": 15, "Bonk Battalion": 5}},
    {"name": "The Unreasonable Clearing", "description": "geometry makes no sense here",
     "faction_bonus": {"Dreamweavers": 10}},
    {"name": "The Screaming Meadow", "description": "the grass yells compliments",
     "faction_bonus": {"Chaos Choir": 10, "Mushroom Union": -5}},
]

# ============================================================
# ITEMS
# ============================================================

ITEMS = [
    {"name": "Glowing Cap", "description": "a bioluminescent mushroom cap", "shiny": True, "value": 10},
    {"name": "Sacred Spore", "description": "a spore that whispers secrets", "shiny": True, "value": 8},
    {"name": "Bonk Hammer", "description": "for maximum bonking", "shiny": False, "value": 5},
    {"name": "Sacred Anvil", "description": "where sacred bonks are forged", "shiny": False, "value": 7},
    {"name": "Golden Acorn", "description": "a truly shiny acorn", "shiny": True, "value": 15},
    {"name": "Crystal Shard", "description": "refracts dreams", "shiny": True, "value": 12},
    {"name": "Pocket Void", "description": "contains a small universe", "shiny": True, "value": 20},
    {"name": "Void Pearl", "description": "black but somehow shiny", "shiny": True, "value": 18},
    {"name": "Dream Stone", "description": "glows when you sleep", "shiny": True, "value": 14},
    {"name": "Haunted Leaf", "description": "whispers in the wind", "shiny": False, "value": 3},
    {"name": "Moss Blanket", "description": "soft and alive", "shiny": False, "value": 2},
    {"name": "Warrior's Shield", "description": "for blocking bonks", "shiny": False, "value": 6},
    {"name": "Screaming Stone", "description": "yells when thrown", "shiny": False, "value": 4},
    {"name": "Chaos Bell", "description": "rings with discord", "shiny": True, "value": 9},
    {"name": "Noisy Rock", "description": "makes noise when bonked", "shiny": False, "value": 3},
    {"name": "Forbidden Berry", "description": "glows faintly", "shiny": True, "value": 11},
]

# Item values for trading
ITEM_VALUES = {item["name"]: item["value"] for item in ITEMS}

# ============================================================
# DEFAULT IDENTITY
# ============================================================

DEFAULT_IDENTITY = {
    "name": "Lonk",
    "emotion": {
        "power": 50, "courage": 50, "wisdom": 50,
        "masochism": 0, "joy": 50, "anxiety": 50
    },
    "personality": {
        "aggression": 50, "curiosity": 50, "anxiety": 50,
        "loyalty": 50, "playfulness": 50
    }
}

# ============================================================
# NAME GENERATOR
# ============================================================

def generate_name():
    prefixes = ["Sn", "Gl", "Br", "Wr", "Fl", "Bl", "Gr", "Kr", "Pl", "Dr", "Tr", "Sh", "Wh", "Ch"]
    suffixes = ["ip", "op", "ub", "ink", "onk", "ip", "ob", "iff", "oof", "arp", "orp", "ump", "onk"]
    return random.choice(prefixes) + random.choice(suffixes)

# ============================================================
# STABILIZER SYSTEM
# ============================================================

class Stabilizer:
    def __init__(self):
        self.bad_patterns = [
            ("bonk", 0.3), ("poop", 0.2), ("fuck", 0.1), ("shit", 0.1),
            ("cunt", 0.05), ("bitch", 0.15), ("dick", 0.1)
        ]

    def stabilize(self, text):
        for pattern, prob in self.bad_patterns:
            if pattern in text.lower() and random.random() < prob:
                return text.replace(pattern, "shiny")
        return text

STABILIZER = Stabilizer()

# ============================================================
# XEMBRA VITALS (NTK-based cognitive core)
# ============================================================

class XembraVitals:
    def __init__(self):
        self.trace = 0.5
        self.entropy = 0.5
        self.coherence = 0.5
        self.drift = 0.1
        self.dream_intensity = 0.1
        self.last_state = None
        self.ema_alpha = 0.1

    def update(self, state_vec):
        if self.last_state is None:
            self.last_state = state_vec
            return

        # Calculate change from last state
        delta = np.array(state_vec) - np.array(self.last_state)
        self.drift = self.ema_alpha * np.linalg.norm(delta) + (1 - self.ema_alpha) * self.drift

        # Calculate entropy of state distribution
        state_array = np.array(state_vec)
        probs = np.abs(state_array) + 1e-10
        probs = probs / np.sum(probs)
        self.entropy = -np.sum(probs * np.log(probs + 1e-10))

        # Calculate coherence (eigenvalue spread of state covariance)
        if len(state_vec) >= 2:
            cov = np.cov(np.array([state_vec, self.last_state]))
            eigvals = np.linalg.eigvalsh(cov)
            if len(eigvals) > 0:
                self.coherence = 1.0 - (np.max(eigvals) - np.min(eigvals)) / (np.sum(eigvals) + 1e-10)
            self.coherence = np.clip(self.coherence, 0, 1)

        # Update trace (EMA of state magnitude)
        self.trace = self.ema_alpha * np.mean(np.abs(state_array)) + (1 - self.ema_alpha) * self.trace

        # Dream intensity based on entropy and drift
        self.dream_intensity = np.clip(self.entropy * self.drift * 10, 0, 1)

        self.last_state = state_vec

    def get_vitals(self):
        return {
            "trace": self.trace,
            "entropy": self.entropy,
            "coherence": self.coherence,
            "drift": self.drift,
            "dream_intensity": self.dream_intensity
        }

DialogueGenerator.EMOTION_WORDS.update(XEMBRA_EMOTIONS)

# ============================================================
# TINY NEURAL NETWORK (FIXED: output_size=6, proper serialization)
# ============================================================

class TinyNN:
    def __init__(self, input_size=INPUT_SIZE, hidden_size=HIDDEN_SIZE, output_size=OUTPUT_SIZE):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.W1 = np.random.randn(input_size, hidden_size) * 0.1
        self.b1 = np.zeros(hidden_size)
        self.W2 = np.random.randn(hidden_size, output_size) * 0.1
        self.b2 = np.zeros(output_size)
        # Critic head: estimates the value of a state, so actions are judged
        # by how much better than expected they turned out (advantage)
        self.Wv = np.random.randn(hidden_size) * 0.1
        self.bv = 0.0
        self.td_scale = 0.1  # running mean |TD error|, normalises step size
        self.updates = 0
        self.last_hidden = None
        self.last_output = None

    def value(self, x):
        x = np.asarray(x, dtype=float)
        hidden = np.maximum(0, np.dot(x, self.W1) + self.b1)
        return float(np.dot(hidden, self.Wv) + self.bv)

    def forward(self, x):
        if isinstance(x, list):
            x = np.array(x)
        hidden = np.maximum(0, np.dot(x, self.W1) + self.b1)
        output = np.dot(hidden, self.W2) + self.b2
        self.last_hidden = hidden
        self.last_output = output
        return hidden, output

    def backward(self, x, action, reward, next_x=None):
        """One-step actor-critic update (TD advantage policy gradient)."""
        if isinstance(x, list):
            x = np.array(x)
        hidden, output = self.forward(x)

        exp_output = np.exp(output - np.max(output))
        probs = exp_output / np.sum(exp_output)

        # TD error: did this turn out better or worse than the critic expected?
        v = float(np.dot(hidden, self.Wv) + self.bv)
        v_next = self.value(next_x) if next_x is not None else 0.0
        td = reward + TD_GAMMA * v_next - v
        self.td_scale = 0.99 * self.td_scale + 0.01 * abs(td)
        adv = float(np.clip(td / max(self.td_scale, 0.05), -3.0, 3.0))

        # Actor: raise log-prob of the action in proportion to its advantage,
        # plus an entropy bonus so the policy doesn't collapse
        onehot = np.zeros(self.output_size)
        onehot[action] = 1.0
        d_logits = adv * (probs - onehot)
        entropy = -np.sum(probs * np.log(probs + 1e-9))
        d_logits += ENTROPY_BONUS * probs * (np.log(probs + 1e-9) + entropy)

        # Critic: move V(s) toward the bootstrapped target
        d_v = -adv

        d_hidden = np.dot(d_logits, self.W2.T) + CRITIC_WEIGHT * d_v * self.Wv
        d_hidden[hidden <= 0] = 0

        self.W2 -= LEARNING_RATE * np.outer(hidden, d_logits)
        self.b2 -= LEARNING_RATE * d_logits
        self.Wv -= LEARNING_RATE * CRITIC_WEIGHT * d_v * hidden
        self.bv -= LEARNING_RATE * CRITIC_WEIGHT * d_v
        self.W1 -= LEARNING_RATE * np.outer(x, d_hidden)
        self.b1 -= LEARNING_RATE * d_hidden
        self.updates += 1

    def to_dict(self):
        # FIX: Proper serialization of weights
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "output_size": self.output_size,
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "Wv": self.Wv.tolist(),
            "bv": float(self.bv),
            "td_scale": float(self.td_scale),
            "updates": int(self.updates)
        }

    @classmethod
    def from_dict(cls, data):
        nn = cls(
            input_size=data["input_size"],
            hidden_size=data["hidden_size"],
            output_size=data["output_size"]
        )
        nn.W1 = np.array(data["W1"])
        nn.b1 = np.array(data["b1"])
        nn.W2 = np.array(data["W2"])
        nn.b2 = np.array(data["b2"])
        # Older saves have no critic; keep the fresh one
        if "Wv" in data:
            nn.Wv = np.array(data["Wv"])
            nn.bv = data.get("bv", 0.0)
            nn.td_scale = data.get("td_scale", 0.1)
            nn.updates = data.get("updates", 0)
        return nn

    def choose_action(self, state):
        _, output = self.forward(state)
        probs = np.exp(output - np.max(output))
        probs = probs / np.sum(probs)
        return np.random.choice(self.output_size, p=probs)

# ============================================================
# EXPERIENCE BUFFER (FIXED: JSON serializable)
# ============================================================

class ExperienceBuffer:
    def __init__(self, capacity=MEMORY_CAPACITY):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)

    def add(self, state, action, reward, next_state):
        self.buffer.append((state, action, reward, next_state))

    def sample(self, batch_size):
        if len(self.buffer) < batch_size:
            return random.sample(self.buffer, len(self.buffer))
        return random.sample(self.buffer, batch_size)

    def __len__(self):
        return len(self.buffer)

    def to_dict(self):
        # FIX: Convert numpy arrays to lists for JSON serialization
        return {
            "capacity": self.capacity,
            "buffer": [
                [
                    s.tolist() if hasattr(s, 'tolist') else s,
                    a,
                    r,
                    s2.tolist() if hasattr(s2, 'tolist') else s2
                ]
                for s, a, r, s2 in self.buffer
            ]
        }

    @classmethod
    def from_dict(cls, data):
        # FIX: __init__ only accepts capacity - construct, then refill.
        # (This bug broke world load and soul inheritance.)
        buf = cls(capacity=data.get("capacity", MEMORY_CAPACITY))
        for s, a, r, s2 in data.get("buffer", []):
            buf.buffer.append((np.array(s), a, r, np.array(s2)))
        return buf

    def clear(self):
        self.buffer.clear()

# ============================================================
# REWARD SYSTEM
# ============================================================

class RewardSystem:
    def __init__(self):
        self.last_health = MAX_HEALTH
        self.last_emotion = {}
        self.last_vitals = {}
        self.last_anxiety = None
        self.last_social = None
        self.last_vocab = None

    def calculate_reward(self, lonk):
        if not REWARD_V2:
            return self._calculate_reward_v1(lonk)

        reward = 0.0

        # Health: tanh-squashed so one big hit hurts without swamping every
        # other signal; healing is rewarded symmetrically
        health_diff = lonk.health - self.last_health
        reward += 0.5 * np.tanh(health_diff / 10.0)
        self.last_health = lonk.health
        # Staying in good shape matters, not just the change
        reward += 0.05 * (lonk.health / getattr(lonk, 'max_health', MAX_HEALTH) - 0.5)

        # Emotion changes (joy/courage/power/wisdom), small and bounded
        for key in ["joy", "courage", "power", "wisdom"]:
            val = lonk.emotion.get(key, 50)
            prev = self.last_emotion.get(key, val)
            reward += float(np.clip((val - prev) * 0.01, -0.1, 0.1))
            self.last_emotion[key] = val

        # Anxiety: penalise it rising, reward it falling (not its absolute level,
        # which used to hand every calm Lonk a free constant bonus)
        anxiety = lonk.emotion.get("anxiety", 50)
        prev_anx = self.last_anxiety if self.last_anxiety is not None else anxiety
        reward -= float(np.clip((anxiety - prev_anx) * 0.01, -0.1, 0.1))
        self.last_anxiety = anxiety

        # Vitals
        vitals = lonk.brain.vitals.get_vitals()
        for key in ["trace", "coherence"]:
            val = vitals.get(key, 0.5)
            prev = self.last_vitals.get(key, val)
            reward += (val - prev) * 0.05
            self.last_vitals[key] = val

        # Social: warmer relationships are good, damaged ones are bad. Uses the
        # summed relationship score (smooth) rather than a friend-count threshold,
        # which almost never triggers
        social = sum(lonk.relationships.values())
        prev_s = self.last_social if self.last_social is not None else social
        reward += 0.03 * float(np.clip(social - prev_s, -10, 10))
        self.last_social = social

        # Knowledge: learning a new word is intrinsically rewarding
        vocab = len(lonk.vocabulary)
        prev_v = self.last_vocab if self.last_vocab is not None else vocab
        reward += 0.05 * float(np.clip(vocab - prev_v, 0, 3))
        self.last_vocab = vocab

        # Small living reward
        reward += 0.01

        return float(np.clip(reward, -1.0, 1.0))

    def _calculate_reward_v1(self, lonk):
        reward = 0.0

        # Health reward
        health_diff = lonk.health - self.last_health
        reward += health_diff * 0.1
        self.last_health = lonk.health

        # Emotion reward (higher joy/courage = positive)
        for key in ["joy", "courage", "power", "wisdom"]:
            val = lonk.emotion.get(key, 50)
            prev = self.last_emotion.get(key, 50)
            reward += (val - prev) * 0.01
            self.last_emotion[key] = val

        # Vitals reward
        vitals = lonk.brain.vitals.get_vitals()
        for key in ["trace", "coherence"]:
            val = vitals.get(key, 0.5)
            prev = self.last_vitals.get(key, 0.5)
            reward += (val - prev) * 0.05
            self.last_vitals[key] = val

        # Penalty for high anxiety
        anxiety = lonk.emotion.get("anxiety", 50)
        reward -= (anxiety - 50) * 0.01

        # Small living reward
        reward += 0.01

        # Clamp reward
        return np.clip(reward, -1.0, 1.0)

# ============================================================
# LONK DYNAMICS (Psi, theta, A, V, P model)
# ============================================================

class LonkDynamics:
    def __init__(self):
        self.Psi = 0.5  # Core energy
        self.theta = 0.5  # Expectation
        self.A = 0.2  # Arousal
        self.V = 0.3  # Valence
        self.P = 0.1  # Prediction error
        self.alpha = 0.1  # Learning rate

    def step(self, state, s_t, pain_t, learning_t=0.0, baseline_arousal=0.3):
        Psi, theta, A, V, P = state

        # Update based on stimuli
        dPsi = self.alpha * (s_t - Psi)
        dtheta = self.alpha * (s_t - theta)
        dA = self.alpha * (min(1.0, baseline_arousal + 0.65 * learning_t) - A)
        dV = self.alpha * (np.clip(s_t - 0.3 * pain_t, 0, 1) - V)
        dP = self.alpha * (abs(s_t - theta) - P)

        # Clamp to [0, 1]
        Psi = np.clip(Psi + dPsi, 0, 1)
        theta = np.clip(theta + dtheta, 0, 1)
        A = np.clip(A + dA, 0, 1)
        V = np.clip(V + dV, 0, 1)
        P = np.clip(P + dP, 0, 1)

        return [Psi, theta, A, V, P]

    def get_state(self):
        return [self.Psi, self.theta, self.A, self.V, self.P]

# ============================================================
# LONK BRAIN (Neural learning + emotional state)
# ============================================================

class LonkBrain:
    def __init__(self, name):
        self.name = name
        self.nn = TinyNN(input_size=INPUT_SIZE, hidden_size=HIDDEN_SIZE, output_size=OUTPUT_SIZE)
        self.buffer = ExperienceBuffer(capacity=MEMORY_CAPACITY)
        self.reward_system = RewardSystem()
        self.vitals = XembraVitals()
        self.state_vec = None
        self.last_state = None
        self.last_action = None
        self.last_reward = 0.0

    def choose_action(self, lonk):
        state = self.get_state_vector(lonk)
        return self.nn.choose_action(state)

    def get_state_vector(self, lonk):
        """Build 32-dimensional state vector for neural network"""
        state = np.zeros(INPUT_SIZE)

        # Emotional state (5 dim: Psi, theta, A, V, P)
        Psi, theta, A, V, P = lonk.state
        state[:5] = [Psi, theta, A, V, P]

        # Personality (5 dim: aggression, curiosity, anxiety, loyalty, playfulness)
        for i, key in enumerate(["aggression", "curiosity", "anxiety", "loyalty", "playfulness"]):
            state[5 + i] = lonk.personality.get(key, 50) / 100.0

        # Health and age (2 dim)
        state[10] = lonk.health / getattr(lonk, "max_health", MAX_HEALTH)
        state[11] = min(lonk.age / 100.0, 1.0)  # Normalized age

        # Runtime registries include cults, annexes and settlements.
        civilization = getattr(lonk.world, 'civilization', None)
        factions = list(civilization.factions) if civilization else [f['name'] for f in FACTIONS]
        rooms = list(civilization.rooms) if civilization else [r['name'] for r in TERRITORIES]
        if lonk.faction in factions:
            state[12] = factions.index(lonk.faction) / max(1, len(factions))
        if lonk.territory in rooms:
            state[13] = rooms.index(lonk.territory) / max(1, len(rooms))

        # Items (2 dim: count, shiny count)
        state[14] = min(len(lonk.items) / 10.0, 1.0)
        # FIX: Use item.get("shiny", False) instead of getattr
        shiny_items = sum(1 for item in lonk.items if item.get("shiny", False))
        state[15] = min(shiny_items / 10.0, 1.0)

        # Social (3 dim: friend count, enemy count, relationship strength)
        friends = sum(1 for v in lonk.relationships.values() if v > lonk.friend_threshold)
        enemies = sum(1 for v in lonk.relationships.values() if v < lonk.grudge_threshold)
        state[16] = min(friends / 10.0, 1.0)
        state[17] = min(enemies / 10.0, 1.0)
        state[18] = min(abs(sum(lonk.relationships.values())) / 1000.0, 1.0)

        # Gossip (1 dim: gossip count)
        state[19] = min(len(lonk.gossip) / MAX_GOSSIP, 1.0)

        # Religion (2 dim: has religion, faith level)
        state[20] = 1.0 if lonk.religion else 0.0
        state[21] = lonk.faith / 100.0

        # Finance (2 dim: coins, inventory value)
        state[22] = min(lonk.coins / 100.0, 1.0)
        state[23] = min(lonk.inventory_value / 100.0, 1.0)

        # Vitals (5 dim: trace, entropy, coherence, drift, dream_intensity)
        vitals = self.vitals.get_vitals()
        state[24] = vitals.get("trace", 0.5)
        state[25] = vitals.get("entropy", 0.5)
        state[26] = vitals.get("coherence", 0.5)
        state[27] = vitals.get("drift", 0.1)
        state[28] = vitals.get("dream_intensity", 0.1)

        # Random exploration (2 dim: small noise)
        # FIX: Reduced noise to prevent learning degradation
        state[29:31] = np.random.randn(2) * 0.001

        # Normalize state
        state = np.clip(state, -1, 1)

        self.state_vec = state
        return state

    def get_emotional_state(self):
        """Get current Xembra emotional state based on brain state"""
        if not hasattr(self, 'state_vec') or self.state_vec is None:
            return "peaceful"

        # Map state dimensions to emotions
        Psi, theta, A, V, P = self.state_vec[:5]
        arousal = A
        valence = V

        # Find closest emotion in XEMBRA_EMOTIONS
        best_emotion = "peaceful"
        best_dist = float('inf')

        for emotion, props in XEMBRA_EMOTIONS.items():
            dist = abs(props["arousal"] - arousal) + abs(props["valence"] - valence)
            if dist < best_dist:
                best_dist = dist
                best_emotion = emotion

        return best_emotion

    def get_need(self, lonk):
        """Determine current need based on emotional state"""
        emotional_state = self.get_emotional_state()
        health_ratio = lonk.health / getattr(lonk, "max_health", MAX_HEALTH)

        # FIX: Removed dead emotion branches (xenoanger, xenohate, etc.)
        if emotional_state in ["xenofear", "afraid"]:
            return "comfort"
        if emotional_state in ["xenolethargic", "sad"]:
            return "reassurance"
        if emotional_state in ["xenojoy", "joyful", "happy"]:
            return "company"
        if emotional_state in ["xenophilous", "curious"]:
            return "knowledge"
        if health_ratio < 0.3:
            return "healing"
        if health_ratio < 0.6:
            return "stability"
        if not lonk.items:
            return "items"
        if not lonk.territory:
            return "territory"
        if len(lonk.relationships) < 2:
            return "company"
        if random.random() < 0.1:
            return random.choice(["comfort", "stability", "knowledge", "company"])
        return "idle"

    def record(self, state, action, reward, next_state):
        self.buffer.add(state, action, reward, next_state)
        self.learn()

    def learn(self):
        if len(self.buffer) < BATCH_SIZE:
            return

        batch = self.buffer.sample(BATCH_SIZE)
        for state, action, reward, next_state in batch:
            self.nn.backward(state, action, reward, next_state)

    def instinct_strength(self):
        """1.0 for a newborn, fading toward MIN_INSTINCT as the net trains."""
        fade = min(1.0, self.nn.updates / INSTINCT_FADE_UPDATES)
        return 1.0 - (1.0 - MIN_INSTINCT) * fade

    def update_vitals(self, state_vec):
        self.vitals.update(state_vec)

    def to_dict(self):
        return {
            "nn": self.nn.to_dict(),
            "buffer": self.buffer.to_dict(),
            "vitals": {
                "trace": self.vitals.trace,
                "entropy": self.vitals.entropy,
                "coherence": self.vitals.coherence,
                "drift": self.vitals.drift,
                "dream_intensity": self.vitals.dream_intensity
            }
        }

    @classmethod
    def from_dict(cls, data, name):
        brain = cls(name)
        if "nn" in data:
            brain.nn = TinyNN.from_dict(data["nn"])
        if "buffer" in data:
            brain.buffer = ExperienceBuffer.from_dict(data["buffer"])
        if "vitals" in data:
            vitals_data = data["vitals"]
            brain.vitals.trace = vitals_data.get("trace", 0.5)
            brain.vitals.entropy = vitals_data.get("entropy", 0.5)
            brain.vitals.coherence = vitals_data.get("coherence", 0.5)
            brain.vitals.drift = vitals_data.get("drift", 0.1)
            brain.vitals.dream_intensity = vitals_data.get("dream_intensity", 0.1)
        return brain

# ============================================================
# LONK CLASS (Main agent)
# ============================================================

class Lonk:
    ACTIONS = ["idle", "explore", "think", "attack", "speak", "trade"]

    # Action primitives for composable system
    VERBS = {
        "bonk": {"category": "violent", "base_reward": -0.1},
        "give": {"category": "social", "base_reward": 0.2},
        "whisper": {"category": "social", "base_reward": 0.1},
        "lick": {"category": "social", "base_reward": 0.15},
        "polish": {"category": "ritual", "base_reward": 0.1},
        "trade": {"category": "economic", "base_reward": 0.2},
        "scream": {"category": "violent", "base_reward": -0.05},
        "consume": {"category": "ritual", "base_reward": 0.1},
        "preach": {"category": "social", "base_reward": 0.15},
        "teach": {"category": "social", "base_reward": 0.2},
        "attack": {"category": "violent", "base_reward": -0.1},
        "praise": {"category": "social", "base_reward": 0.2},
        "insult": {"category": "violent", "base_reward": -0.15},
        "help": {"category": "social", "base_reward": 0.25},
        "dream": {"category": "rest", "base_reward": 0.1},
    }

    MODIFIERS = {
        "with fury": -0.1,
        "secretly": 0.05,
        "loudly": -0.05,
        "gently": 0.1,
        "with love": 0.2,
        "with hate": -0.2,
        "quickly": 0.05,
        "slowly": -0.05,
        "with joy": 0.15,
    }

    def __init__(self, name=None, world=None, _loading=False):
        # Basic attributes
        self.name = name if name else generate_name()
        self.semantic_id = uuid.uuid4().hex
        self.world = world
        self.alive = True
        self.age = 0
        self.generation = 1
        self.max_health = MAX_HEALTH
        self.health = self.max_health
        minimum, maximum = self._lifespan_bounds()
        self.lifespan = random.randint(minimum, maximum)
        self.lifecycle_version = 2
        self.last_aged_tick = None
        self.death_cause = None
        self.trauma = 0
        self.learning_signal = 0.0
        self.action_valence = 0.0
        self.faction = None
        self.territory = None
        self.location_reason = None
        self.rival = None
        self.target = None
        self.pending_retaliation = None  # FIX: Queue retaliation
        self.last_combat_tick = -100

        # Initialize brain and learning
        self.brain = LonkBrain(self.name)
        self.state_vec = None

        # Emotional dynamical state (Psi, theta, A, V, P)
        self.dynamics = LonkDynamics()
        self.state = [0.5, 0.5, 0.2, 0.3, 0.1]  # Psi, theta, A, V, P

        # Emotion dictionary
        self.emotion = {
            "power": 50, "courage": 50, "wisdom": 50,
            "masochism": 0, "joy": 50, "anxiety": 50
        }

        # Personality traits
        self.personality = {
            "aggression": random.randint(30, 70),
            "curiosity": random.randint(30, 70),
            "anxiety": random.randint(30, 70),
            "loyalty": random.randint(30, 70),
            "playfulness": random.randint(30, 70)
        }

        # Habits
        self.habits = {a: 0 for a in self.ACTIONS}

        # Memory systems
        self.memory = {
            "player_words": set(),
            "lonk_words": set(),
            "events": [],
            "player_interactions": [],
        }
        self.long_memory = []
        self.vocabulary = {}
        self.language = {}

        # Social
        self.relationships = {}
        self.grudges = {}
        self.friend_threshold = 20
        self.grudge_threshold = -15
        self.social_memory_decay = 0.98
        self.crush = None
        self.catchphrase = None

        # Gossip
        self.gossip = []
        self.max_gossip = MAX_GOSSIP

        # Items & inventory (using only self.items)
        self.items = []
        self.inventory = []  # Legacy, kept for compatibility

        # Learning state
        self.knowledge = set()
        self.teachings = []

        # Composable action system
        self.known_verbs = dict(self.VERBS)  # Start with all default verbs
        self.action_weights = {}
        self.action_history = []
        self.named_combos = set()  # FIX: Track named combos to prevent spam
        self._init_default_verbs()

        # Religion
        self.religion = None
        self.faith = random.randint(30, 100)
        self.heretic = False

        # Finance
        self.coins = 0
        self.inventory_value = 0

        # Weight-space programming experiment
        self.blessed = False
        self.wp_role = None  # "chosen" (edited) or "control" (never edited)
        self.reward_history = deque(maxlen=WP_HISTORY)

        # --- Autonomous epistemology (v11) ---
        # Axioms the lonk writes itself, its self-made values, and the
        # question (paradigm) it currently lives inside.
        self.axioms = []               # live hypotheses: feature/outcome/evidence
        self.pending_predictions = []  # (axiom, predicted outcome) awaiting reality
        self.will = {a: 1.0 for a in self.ACTIONS}  # self-generated values over actions
        self.skepticism = 0.5          # its OWN rule for what counts as proof
        self.paradigm = "how do I keep living?"    # its driving question
        self.paradigm_focus = "health"              # feature family it probes hardest
        self.epi_stats = {"written": 0, "canonized": 0, "falsified": 0,
                          "shifts": 0, "recent_falsified": 0, "last_shift": -999}
        self._epi_health_prev = getattr(self, "health", MAX_HEALTH)
        self._epi_reward_recent = deque(maxlen=20)
        self._epi_seen_features = {}  # feature -> times experienced
        self._epi_seen_outcomes = {}  # outcome -> times experienced

        # FIX: Skip initialization prints when loading from dict
        if not _loading:
            self.ensure_emotion_keys()
            self.ensure_personality_keys()
            self.join_random_faction()
            self.wander()
            self.init_social()

        # Phase 2: Conversation and Dialogue System (v14)
        # Multi-turn dialogue tracking between this Lonk and others
        self.active_conversations = {}  # target_name -> Conversation
        self.conversation_history = []  # past Conversation objects
        self.dialogue_memory = deque(maxlen=20)  # Recent dialogue topics
        self.dialogue_generator = DialogueGenerator(self)  # Response engine
        
        # Phase 3: Inner Monologue System
        # Autonomous thoughts and inner dialogue
        self.inner_monologue = LonkInnerMonologue(self.name)
        self.inner_thoughts = []  # Direct access to recent thoughts


    def _init_default_verbs(self):
        """Initialize default verb weights"""
        for verb in self.known_verbs:
            for target_type in ["self", "other", "item"]:
                for modifier in list(self.MODIFIERS.keys()) + [None]:
                    key = f"{verb}+{target_type}+{modifier or ''}"
                    self.action_weights[key] = 1.0

    # ============================================================
    # CORE METHODS
    # ============================================================

    def ensure_emotion_keys(self):
        defaults = {
            "power": 50, "courage": 50, "wisdom": 50,
            "masochism": 0, "joy": 50, "anxiety": 50
        }
        for k, v in defaults.items():
            self.emotion.setdefault(k, v)

    def ensure_personality_keys(self):
        defaults = {
            "aggression": 50, "curiosity": 50, "anxiety": 50,
            "loyalty": 50, "playfulness": 50
        }
        for k, v in defaults.items():
            self.personality.setdefault(k, v)

    def join_random_faction(self):
        if FACTIONS:
            faction = random.choice(FACTIONS)
            self.faction = faction["name"]
            print(f"🏳️ {self.name} joins the faction: {self.faction}!")

    def wander(self):
        old_room = self.territory
        civilization = getattr(self.world, 'civilization', None)
        if civilization and old_room in civilization.rooms:
            neighbors = civilization.edges.get(old_room, [])
            if neighbors:
                civilization.move(self, random.choice(neighbors), 'wandering')
                territory = next((t for t in TERRITORIES if t['name'] == self.territory), {})
                if self.faction and self.faction in territory.get('faction_bonus', {}):
                    print(f"✨ {self.name} feels empowered by {self.faction}'s sacred ground!")
                    self.emotion['joy'] += 10
                    self.emotion['power'] += 5
            return
        if TERRITORIES:
            territory = random.choice(TERRITORIES)
            self.territory = territory["name"]
            self.location_reason = {"kind": "wandering", "place": self.territory}
            civilization = getattr(self.world, 'civilization', None)
            if civilization and self.territory != old_room and hasattr(self, 'dialogue_generator'):
                civilization.on_enter(self)
            print(f"🌍 {self.name} wanders into {self.territory} — {territory['description']}")
            # FIX: Check self.faction in territory faction_bonus, not self.territory
            if self.faction and self.faction in territory.get("faction_bonus", {}):
                bonus = territory["faction_bonus"][self.faction]
                print(f"✨ {self.name} feels empowered by {self.faction}'s sacred ground!")
                self.emotion["joy"] += 10
                self.emotion["power"] += 5

    def init_social(self):
        self.memory.setdefault("player_interactions", [])
        self.memory.setdefault("player_words", set())
        self.catchphrase = getattr(self, "catchphrase", None)
        self.crush = getattr(self, "crush", None)
        self.grudges = getattr(self, "grudges", {})

    # ============================================================
    # ACTION SYSTEM (FIXED)
    # ============================================================

    def choose_action(self):
        """Choose actions with cooperative alternatives to needless conflict."""
        action_idx = self.brain.choose_action(self)
        # Remember the state this decision was made in, for credit assignment
        self._decision_state = np.array(self.brain.state_vec)
        action_map = {0: "idle", 1: "explore", 2: "think", 3: "attack", 4: "speak", 5: "trade"}
        action = action_map.get(action_idx, "idle")
        civilization = getattr(self.world, 'civilization', None)
        if civilization:
            intention = civilization.intent(self)
            if intention:
                verb = intention['verb']
                self.habits[verb] = self.habits.get(verb, 0) + 1
                return intention

        # VALUE AUTONOMY: sometimes the lonk follows its self-made will
        # instead of the trained network (v11)
        if EPISTEMOLOGY_ON and random.random() < EPI_WILL_STRENGTH:
            weights = [self.will.get(a, 1.0) for a in self.ACTIONS]
            if sum(weights) > 0:
                action = random.choices(self.ACTIONS, weights=weights, k=1)[0]

        need = self.brain.get_need(self)
        # Instincts yield to the learned policy as the brain gains experience
        instinct = self.brain.instinct_strength()
        if random.random() >= instinct:
            need = "idle"

        # AGGRESSIVE OVERRIDES (probabilities from VIOLENCE config)
        if need == "items":
            if random.random() < 0.4:
                action = "trade"
            elif random.random() < 0.4:
                action = "explore"
            elif random.random() < _v("items_attack"):
                action = "attack"
        elif need in ["comfort", "stability", "reassurance"]:
            if random.random() < _v("discomfort_attack"):
                action = "attack"
            else:
                action = "speak"
        elif need == "knowledge":
            if random.random() < _v("knowledge_attack"):
                action = "attack"
        elif need == "territory":
            if random.random() < _v("territory_attack"):
                action = "attack"

        # RANDOM VIOLENCE (tunable, was hardcoded 20%)
        if random.random() < _v("random_attack") * instinct:
            action = "attack"

        if action == 'attack':
            enemies = [score for score in self.relationships.values() if score < -10]
            willingness = 0.35 if enemies else 0.06
            if not TOGGLES.get('violence', True) or random.random() > willingness:
                action = self.choose_cooperative_action()
        elif action in ('speak', 'trade') and random.random() < 0.4:
            action = self.choose_cooperative_action()

        self.habits[action] = self.habits.get(action, 0) + 1
        return action

    def _same_room(self, other):
        civilization = getattr(self.world, 'civilization', None)
        rooms = getattr(civilization, 'rooms', {})
        if isinstance(rooms, dict) and self.territory in rooms and getattr(other, 'territory', None) in rooms:
            return self.territory == other.territory
        return True  # Legacy worlds without a location graph.

    def nearby_lonks(self):
        return [p for p in getattr(self.world, 'lonks', [])
                if p is not self and p.alive and self._same_room(p)]

    def choose_cooperative_action(self):
        peers = self.nearby_lonks()
        if any(p.health < getattr(p, 'max_health', MAX_HEALTH) - 10 or p.trauma > 8 for p in peers):
            return 'help'
        if self.items and any(not p.items for p in peers):
            return 'give'
        if any(set(self.vocabulary) - set(p.vocabulary) for p in peers):
            return 'teach'
        return random.choice(('speak', 'explore', 'think', 'trade' if self.items else 'explore'))

    def act(self, action=None):
        """Execute an action"""
        if not self.alive:
            return

        self.age_tick()
        if not self.alive:  # FIX: Check again after potential death
            return

        # RANDOM COMBAT: occasional bonus duel (tunable, was hardcoded 15%)
        if random.random() < _v("random_combat") and self.world:
            others = self.nearby_lonks()
            if others:
                target = random.choice(others)
                self.rival = target
                self._narrate(f"💥 {self.name} RANDOMLY ATTACKS {target.name}!")
                self.duel()

        # FIX: Queue retaliation at start of tick
        if hasattr(self, 'pending_retaliation') and self.pending_retaliation:
            self.rival = self.pending_retaliation
            self.duel()
            self.pending_retaliation = None

        # FIX: Convert action to proper format
        if action is None:
            action = self.choose_action()
        elif isinstance(action, str):
            # Convert old-style string action to new composable format
            action = {
                "verb": action,
                "target_type": "other",
                "object": None,
                "modifier": None
            }

        # Execute based on action type
        if isinstance(action, dict):
            self.execute_action(action)
        elif isinstance(action, str):
            # Fallback for old-style actions
            if action == "idle":
                self.idle()
            elif action == "explore":
                self.wander()
                self.find_item()
            elif action == "think":
                self.think()
            elif action == "attack":
                self.choose_rival()
                self.duel()
            elif action == "speak":
                self.speak_to_random()
            elif action == "trade":
                self.try_trade()
            else:
                self.idle()
        else:
            self.idle()

        # Random religious/financial behaviors
        if random.random() < 0.05:
            self.perform_ritual()
        if random.random() < 0.05:
            self.create_myth()

        # Social behaviors
        self.maybe_talk_to_player()
        self.maybe_gossip_about_player()
        self.maybe_develop_catchphrase()
        self.check_grudges()
        self.maybe_gossip()
        self.maybe_share_vocabulary()
        self.maybe_interact()
        self.maybe_teach_verbs()  # FIX: Now with correct probability

        # FIX: update_vitals() called once per tick
        self.update_vitals()
        state = self.brain.get_state_vector(self)
        reward = self.brain.reward_system.calculate_reward(self)

        # FIX: Safe ACTIONS.index() with fallback
        chosen_verb = action.get('verb', 'idle') if isinstance(action, dict) else action
        credit = {'help': 'speak', 'teach': 'speak', 'give': 'trade', 'bonk': 'attack',
                  'praise': 'speak', 'insult': 'attack', 'dream': 'think',
                  'proclaim': 'speak', 'follow': 'explore', 'seek': 'trade', 'devote': 'trade', 'jealous': 'speak', 'extort': 'trade'}
        policy_action = credit.get(chosen_verb, chosen_verb)
        action_idx = self.ACTIONS.index(policy_action) if policy_action in self.ACTIONS else 0

        # Learn from the state the decision was made in -> state it led to
        prev_state = getattr(self, "_decision_state", None)
        self._decision_state = None
        if prev_state is None:
            prev_state = state
        self.brain.record(prev_state, action_idx, reward, state)
        self.record_reward(reward)
        # Autonomous epistemology: judge axioms, drift values (v11)
        if isinstance(action, dict):
            verb = action.get("verb", "idle")
        else:
            verb = action if isinstance(action, str) else "idle"
        cat = self.VERBS.get(verb, {}).get("category", None)
        if cat == "violent":
            verb = "attack"
        elif cat == "social":
            verb = "speak"
        elif cat == "economic":
            verb = "trade"
        elif cat in ("ritual", "rest"):
            verb = "think" if cat == "ritual" else "idle"
        if verb not in self.ACTIONS:
            verb = "idle"
        self.epistemic_update(reward, verb)
        self.evolve()

    def execute_action(self, action):
        """Execute a composable action"""
        verb = action.get("verb", "idle")
        target_type = action.get("target_type", "self")
        modifier = action.get("modifier", None)
        obj = action.get("object", None)

        # FIX: Populate obj if None
        if obj is None:
            if verb in ("give", "trade") and self.items:
                obj = random.choice(self.items)
            elif verb in ("whisper", "teach", "preach") and self.vocabulary:
                obj = random.choice(list(self.vocabulary.keys()))
            elif verb in ("bonk", "attack", "lick", "scream", "insult") and self.world:
                others = self.nearby_lonks()
                if others:
                    obj = random.choice(others)
            elif verb in ("polish", "consume") and self.items:
                obj = random.choice(self.items)

        # Determine target
        target = None
        if target_type == "other" and self.world:
            others = self.nearby_lonks()
            explicit = action.get('target_name')
            if explicit:
                target = next((p for p in self.world.lonks if p is not self and p.alive and p.name == explicit), None)
            elif others:
                if verb == 'help':
                    target = max(others, key=lambda p: getattr(p, 'max_health', MAX_HEALTH) - p.health + p.trauma)
                elif verb == 'give':
                    target = min(others, key=lambda p: len(p.items))
                else:
                    target = random.choice(others)
        elif target_type == "self":
            target = self
        elif target_type == "item" and self.items:
            target = random.choice(self.items)

        # Execute based on verb
        verb_method = getattr(self, f"_verb_{verb}", None)
        civilization = getattr(self.world, 'civilization', None)
        if target is not None and hasattr(target, 'territory') and not self._same_room(target) and verb not in ('follow', 'seek'):
            destination = civilization.next_room(self.territory, target.territory)
            if destination == self.territory:
                return {'success': False, 'reward': -0.02}
            civilization.move(self, destination, 'meeting', target.name)
            return {'success': True, 'reward': 0.04, 'travelling': True}
        if civilization and verb in ('proclaim', 'follow', 'seek', 'devote', 'jealous', 'extort'):
            outcome = civilization.act(self, verb, target, obj)
        elif verb_method:
            outcome = verb_method(target, obj, modifier)
        else:
            # FIX: Generic fallback for unimplemented verbs
            outcome = self._verb_fallback(verb, target, obj, modifier)

        # Record outcome and potentially name the action
        self._record_action_outcome(action, outcome)

        return outcome

    def _record_action_outcome(self, action, outcome):
        """Record action outcome and update weights"""
        verb = action.get("verb", "idle")
        target_type = action.get("target_type", "self")
        modifier = action.get("modifier", "") or ""
        obj_name = action.get("object", {}).get("name", "") if isinstance(action.get("object"), dict) else str(action.get("object", ""))
        compound_key = f"{verb}+{target_type}+{modifier}"

        # Update weight with reward
        reward = outcome.get("reward", 0.0)
        self.experience(valence=float(reward))
        # FIX: Add floor to prevent drift to zero
        new_weight = self.action_weights.get(compound_key, 1.0) * (1 + reward * 0.1)
        self.action_weights[compound_key] = max(0.05, new_weight)

        # Record in history
        self.action_history.append({
            "action": action,
            "outcome": outcome,
            "reward": reward,
            "tick": self.world.tick if self.world else 0
        })
        if len(self.action_history) > 100:
            self.action_history.pop(0)

        # Name memorable actions
        if abs(reward) > 0.5:
            self._name_action(action, reward)

    def _name_action(self, action, reward):
        """Invent a new verb name for memorable action combinations"""
        verb = action.get("verb", "idle")
        target_type = action.get("target_type", "self")
        modifier = action.get("modifier", "") or ""
        obj_name = ""

        if isinstance(action.get("object"), dict):
            obj_name = action["object"].get("name", "")
        elif action.get("object"):
            obj_name = str(action["object"])

        compound_name = f"{verb}+{target_type}+{modifier}+{obj_name}"

        # FIX: Check named_combos, not known_verbs
        if compound_name not in self.named_combos:
            self.named_combos.add(compound_name)
            new_verb = self._invent_verb_name()

            # Store the compound action as a new verb
            self.known_verbs[new_verb] = {
                "category": self.known_verbs.get(verb, {}).get("category", "unknown"),
                "base_reward": self.known_verbs.get(verb, {}).get("base_reward", 0.0) * (1 + reward * 0.5),
                "definition": f"{verb} {target_type} {modifier} {obj_name}".strip()
            }

            print(f"💡 {self.name} invents a new verb: '{new_verb}' (means: {self.known_verbs[new_verb]['definition']})")

    def _invent_verb_name(self):
        """Generate a random verb name"""
        prefixes = ["sn", "gl", "br", "wr", "fl", "bl", "gr", "kr", "pl", "dr", "tr", "sh", "wh", "ch", "fr"]
        suffixes = ["urf", "orp", "ink", "onk", "oof", "arp", "iff", "oof", "ump", "onk", "sni", "flo", "mop"]
        return random.choice(prefixes) + random.choice(suffixes)

    def learn_verb(self, verb_name, definition=None):
        """Learn a new verb from another Lonk"""
        MAX_VERBS = 20  # Cap verb inventory

        if definition is None:
            definition = self.VERBS.get(verb_name, {"category": "unknown", "base_reward": 0.0})

        # Add new verb
        if verb_name not in self.known_verbs:
            self.known_verbs[verb_name] = definition
            self.experience(learning=1, valence=0.12)

            # Initialize weights for this verb
            for target_type in ["self", "other", "item"]:
                for modifier in list(self.MODIFIERS.keys()) + [None]:
                    key = f"{verb_name}+{target_type}+{modifier or ''}"
                    self.action_weights[key] = 1.0

        # FIX: Forget least-used VERB (not combo) when at capacity
        if len(self.known_verbs) > MAX_VERBS:
            # Calculate total usage per verb
            verb_usage = {}
            for key, weight in self.action_weights.items():
                base_verb = key.split("+")[0]
                verb_usage[base_verb] = verb_usage.get(base_verb, 0) + weight

            # Find least-used verb
            if verb_usage:
                worst_verb = min(verb_usage, key=verb_usage.get)
                if worst_verb in self.known_verbs:
                    del self.known_verbs[worst_verb]
                    # Remove ALL keys for this verb
                    self.action_weights = {
                        k: w for k, w in self.action_weights.items()
                        if k.split("+")[0] != worst_verb
                    }
                    print(f"🗑️  {self.name} forgets the verb: {worst_verb}")

    def choose_composable_action(self):
        """Choose a composable action based on weights"""
        if not self.action_weights:
            return {"verb": "idle", "target_type": "self", "object": None, "modifier": None}

        # Select a random action key weighted by its weight
        keys = list(self.action_weights.keys())
        weights = list(self.action_weights.values())

        # Normalize weights
        total = sum(weights)
        if total <= 0:
            return {"verb": "idle", "target_type": "self", "object": None, "modifier": None}

        probs = [w / total for w in weights]
        chosen_key = random.choices(keys, weights=probs, k=1)[0]

        # Parse the key
        parts = chosen_key.split("+")
        verb = parts[0]
        target_type = parts[1] if len(parts) > 1 else "self"
        modifier = parts[2] if len(parts) > 2 else None

        return {
            "verb": verb,
            "target_type": target_type,
            "object": None,
            "modifier": modifier
        }

    def maybe_teach_verbs(self):
        """Teach verbs to other Lonks"""
        # FIX: Changed < to > so it teaches 5% of the time, not 95%
        if not self.world or random.random() > 0.02:  # 2% teach rate
            return

        others = self.nearby_lonks()
        if not others:
            return

        target = random.choice(others)

        # Choose a verb to teach (prefer newly invented ones)
        known_verbs_list = list(self.known_verbs.keys())
        if not known_verbs_list:
            return

        # Prefer teaching verbs that aren't in the target's known_verbs
        unknown_verbs = [v for v in known_verbs_list if v not in target.known_verbs]
        if unknown_verbs:
            verb_to_teach = random.choice(unknown_verbs)
        else:
            verb_to_teach = random.choice(known_verbs_list)

        target.learn_verb(verb_to_teach, self.known_verbs[verb_to_teach])
        self._narrate(f"📚 {self.name} teaches {target.name} the verb '{verb_to_teach}'")
        self.update_relationship(target, +2)

    # ============================================================
    # VERB IMPLEMENTATIONS
    # ============================================================

    def _verb_idle(self, target, obj, modifier):
        self.idle()
        return {'success': True, 'reward': 0.02}

    def _verb_explore(self, target, obj, modifier):
        before = len(self.items)
        self.wander()
        self.find_item()
        discoveries = ([self.territory] if self.territory else []) + [item['name'] for item in self.items[before:]]
        for concept in discoveries:
            self.vocabulary.setdefault(concept.lower(), 1)
        self._learn_concepts(discoveries)
        return {'success': True, 'reward': 0.15 if len(self.items) > before else 0.06}

    def _verb_think(self, target, obj, modifier):
        self.think()
        return {'success': True, 'reward': 0.08}

    def _verb_help(self, target, obj, modifier):
        if target is None or target is self or not target.alive or not self._same_room(target):
            return {'success': False, 'reward': -0.02}
        before = target.health
        target.health = min(getattr(target, "max_health", MAX_HEALTH), target.health + 4)
        target.experience(valence=0.3, comfort=3)
        self.update_relationship(target, 3)
        target.update_relationship(self, 3)
        self._narrate(f"{self.name} helps {target.name} recover ({target.health - before} health) and offers comfort.")
        return {'success': True, 'reward': 0.25}

    def _verb_fallback(self, verb, target, obj, modifier):
        """Generic fallback for unimplemented verbs"""
        verb_info = self.known_verbs.get(verb, {})
        cat = verb_info.get("category", "unknown")
        reward = verb_info.get("base_reward", 0.0)

        modifier_str = f" {modifier}" if modifier else ""
        if target and hasattr(target, 'name'):
            print(f"✨ {self.name} {verb}s {target.name}{modifier_str}")
        elif obj:
            obj_name = obj.get("name", str(obj))
            print(f"✨ {self.name} {verb}s {obj_name}{modifier_str}")
        else:
            print(f"✨ {self.name} {verb}s the air{modifier_str}")

        return {"success": True, "reward": reward}

    def _verb_bonk(self, target, obj, modifier):
        """Bonk someone or something"""
        if target is not None and hasattr(target, 'territory') and not self._same_room(target):
            return {'success': False, 'reward': -0.02}
        if not TOGGLES.get('violence', True):
            return {'success': False, 'reward': -0.05}
        modifier_str = f" {modifier}" if modifier else ""

        if target and hasattr(target, 'name') and target != self:
            print(f"💥 {self.name} bonks {target.name}{modifier_str}!")
            target.experience(valence=-0.4, trauma=5)
            target.hear(self, f"{self.name} bonked me{modifier_str}!")
            self.update_relationship(target, -3)
            target.add_grudge(self.name)
            return {"success": True, "reward": -0.05}

        elif obj and isinstance(obj, dict):
            print(f"💥 {self.name} bonks {obj.get('name', 'something')}{modifier_str}!")
            return {"success": True, "reward": 0.05}

        else:
            print(f"💥 {self.name} bonks the air{modifier_str}!")
            return {"success": True, "reward": -0.02}

    def _verb_give(self, target, obj, modifier):
        """Give an item to someone"""
        if not obj or not isinstance(obj, dict):
            return {"success": False, "reward": -0.1}

        if not target or target is self or not hasattr(target, 'items') or not self._same_room(target):
            return {"success": False, "reward": -0.1}

        if obj not in self.items:
            return {"success": False, "reward": -0.1}

        # Perform the give
        self.items.remove(obj)
        target.items.append(obj)
        self.inventory = [item['name'] for item in self.items]
        target.inventory = [item['name'] for item in target.items]
        target.experience(valence=0.5, comfort=2)
        obj_name = obj.get("name", "something")

        modifier_str = f" {modifier}" if modifier else ""
        print(f"🎁 {self.name} gives {obj_name} to {target.name}{modifier_str}!")

        self.update_relationship(target, +5)
        return {"success": True, "reward": 0.3}

    def _verb_whisper(self, target, obj, modifier):
        if target is None or not hasattr(target, 'hear') or not self._same_room(target):
            return {'success': False, 'reward': -0.05}
        message = obj.get('name', '') if isinstance(obj, dict) else str(obj or 'the moss is listening')
        self.last_spoken = message
        self._narrate(f"{self.name} whispers to {target.name}: {message}")
        target.hear(self, message)
        civilization = getattr(self.world, 'civilization', None)
        if civilization:
            civilization.signal(self, message, 'whisper')
        self.update_relationship(target, 2)
        return {'success': True, 'reward': 0.12}

    def _verb_speak(self, target, obj, modifier):
        """Speak to someone - VISIBLE"""
        if not target or not hasattr(target, 'name') or not self._same_room(target):
            return {"success": False, "reward": -0.05}
        message = self.generate_dynamic_response(target=target, context="statement")
        modifier_str = f" {modifier}" if modifier else ""
        self._narrate(f"💬 {self.name} → {target.name}{modifier_str}: {message}")
        target.hear(self, message)
        self.update_relationship(target, +1)
        return {"success": True, "reward": 0.1}

        modifier_str = f" {modifier}" if modifier else ""
        full_message = f"{self.name} whispers{modifier_str}: {message}"
        print(f"🗣️ {full_message}")
        target.hear(self, message)

        self.update_relationship(target, +2)
        return {"success": True, "reward": 0.15}

    def _verb_lick(self, target, obj, modifier):
        """Lick someone or something"""
        modifier_str = f" {modifier}" if modifier else ""

        if target and hasattr(target, 'name'):
            print(f"👅 {self.name} licks {target.name}{modifier_str}!")
            target.hear(self, f"{self.name} licked me{modifier_str}!")
            self.update_relationship(target, +1)
            return {"success": True, "reward": 0.1}

        elif obj and isinstance(obj, dict):
            obj_name = obj.get("name", "something")
            print(f"👅 {self.name} licks {obj_name}{modifier_str}!")
            return {"success": True, "reward": 0.05}

        else:
            print(f"👅 {self.name} licks the air{modifier_str}!")
            return {"success": True, "reward": -0.02}

    def _verb_polish(self, target, obj, modifier):
        """Polish a shiny object (ritual action)"""
        if not obj or not isinstance(obj, dict):
            # Find a shiny item to polish
            shiny_items = [i for i in self.items if i.get("shiny", False)]
            if shiny_items:
                obj = random.choice(shiny_items)
            else:
                return {"success": False, "reward": -0.05}

        obj_name = obj.get("name", "something")
        modifier_str = f" {modifier}" if modifier else ""
        print(f"✨ {self.name} polishes {obj_name}{modifier_str}!")

        # If this is a sacred item for our religion, gain faith
        if self.religion and obj_name in self.religion.get("sacred_items", []):
            self.faith = min(100, self.faith + 5)
            return {"success": True, "reward": 0.25}

        return {"success": True, "reward": 0.1}

    def _verb_trade(self, target, obj, modifier):
        """Trade with someone"""
        if not target or not hasattr(target, 'trade_with'):
            return {"success": False, "reward": -0.1}

        # Use the existing trade_with method
        success = self.trade_with(target)
        return {"success": success, "reward": 0.2 if success else -0.05}

    def _verb_scream(self, target, obj, modifier):
        """Scream (Chaos Choir ritual)"""
        modifier_str = f" {modifier}" if modifier else ""
        civilization = getattr(self.world, 'civilization', None)
        content = obj.get('name', '') if isinstance(obj, dict) else str(obj or '')
        self.last_spoken = content or 'AAAAH'
        if civilization and content:
            civilization.signal(self, content, 'scream')

        if target and hasattr(target, 'name'):
            print(f"😱 {self.name} SCREAMS at {target.name}{modifier_str}: {content or 'AAAAH'}!")
            target.hear(self, f"{self.name} SCREAMED {content or 'AAAAH'} at me{modifier_str}!")
            target.experience(valence=-0.2)
            self.update_relationship(target, -2)
            return {"success": True, "reward": -0.05}
        else:
            print(f"😱 {self.name} SCREAMS into the void{modifier_str}: {content or 'AAAAH'}!")
            return {"success": True, "reward": 0.05}

    def _verb_consume(self, target, obj, modifier):
        """Consume an item (Mycelial Network ritual)"""
        if not obj or not isinstance(obj, dict):
            # Find an item to consume
            if self.items:
                obj = random.choice(self.items)
            else:
                return {"success": False, "reward": -0.1}

        obj_name = obj.get("name", "something")
        self.items.remove(obj)

        modifier_str = f" {modifier}" if modifier else ""
        print(f"🍄 {self.name} consumes {obj_name}{modifier_str}!")

        # If this is a sacred item, gain faith
        if self.religion and obj_name in self.religion.get("sacred_items", []):
            self.faith = min(100, self.faith + 10)
            return {"success": True, "reward": 0.3}

        return {"success": True, "reward": 0.1}

    def _verb_preach(self, target, obj, modifier):
        """Preach to someone"""
        if not target or not hasattr(target, 'name'):
            return {"success": False, "reward": -0.05}

        if self.religion:
            message = f"Join {self.religion['name']}! {self.religion['description']}"
        else:
            message = "Join my religion! It's great!"

        modifier_str = f" {modifier}" if modifier else ""
        print(f"⛪ {self.name} preaches to {target.name}{modifier_str}: {message}")
        target.hear(self, message)

        # Try to convert
        if self.religion:
            self.preach(target)

        return {"success": True, "reward": 0.15}

    def _verb_teach(self, target, obj, modifier):
        """Teach someone a word or concept"""
        if not target or not hasattr(target, 'learn_verb') or not self._same_room(target):
            return {"success": False, "reward": -0.05}

        unknown_words = [word for word in self.vocabulary if word not in target.vocabulary]
        if (not isinstance(obj, str) or obj in target.vocabulary) and unknown_words:
            obj = random.choice(unknown_words)

        if obj and isinstance(obj, str):
            # Teach a word
            if obj not in target.vocabulary:
                target.vocabulary[obj] = 1
                target.experience(learning=1, valence=0.12)
                target.dialogue_generator._learn_words(obj, source=self.name)
                target.knowledge.add(obj)
                self._narrate(f"📚 {self.name} teaches {target.name} the word '{obj}'")
                self.update_relationship(target, +2)
                civilization = getattr(self.world, 'civilization', None)
                if civilization:
                    civilization.signal(self, obj, 'teach')
                return {"success": True, "reward": 0.2}

        # Teach a random verb
        known_verbs_list = [verb for verb in self.known_verbs if verb not in target.known_verbs]
        if known_verbs_list:
            verb_to_teach = random.choice(known_verbs_list)
            target.learn_verb(verb_to_teach, self.known_verbs[verb_to_teach])
            self._narrate(f"📚 {self.name} teaches {target.name} the verb '{verb_to_teach}'")
            self.update_relationship(target, +2)
            return {"success": True, "reward": 0.2}

        return {"success": False, "reward": -0.05}

    def _verb_attack(self, target, obj, modifier):
        """Attack someone (more violent than bonk)"""
        if not target or not hasattr(target, 'react_to_attack') or not self._same_room(target):
            return {"success": False, "reward": -0.1}

        modifier_str = f" {modifier}" if modifier else ""
        self._narrate(f"⚔️  {self.name} attacks {target.name}{modifier_str}!")
        self.rival = target
        self.duel()
        return {"success": True, "reward": -0.1}

    def _verb_praise(self, target, obj, modifier):
        """Praise someone"""
        if not target or not hasattr(target, 'name') or not self._same_room(target):
            return {"success": False, "reward": -0.05}

        modifier_str = f" {modifier}" if modifier else ""
        praise = random.choice([
            "You are amazing!",
            "I love you!",
            "You are the best!",
            "Shiny bless you!",
            "You make me happy!"
        ])
        print(f"💖 {self.name} praises {target.name}{modifier_str}: {praise}")
        target.hear(self, praise)
        target.experience(valence=0.3, comfort=2)
        self.update_relationship(target, +5)
        return {"success": True, "reward": 0.2}

    def _verb_insult(self, target, obj, modifier):
        """Insult someone"""
        if not target or not hasattr(target, 'name') or not self._same_room(target):
            return {"success": False, "reward": -0.05}

        modifier_str = f" {modifier}" if modifier else ""
        insult = random.choice([
            "You are a poop!",
            "I hate you!",
            "You are the worst!",
            "Your mother was a bonk!",
            "You smell like moss!"
        ])
        print(f"😡 {self.name} insults {target.name}{modifier_str}: {insult}")
        target.hear(self, insult)
        target.experience(valence=-0.45)
        self.update_relationship(target, -5)
        target.add_grudge(self.name)
        return {"success": True, "reward": -0.15}

    def _verb_dream(self, target, obj, modifier):
        """Enter dream state"""
        if not TOGGLES.get("dreams", True):
            return {"success": False, "reward": -0.05}

        print(f"💤 {self.name} enters a dreamlike state.")
        dream_message = random.choice([
            f"{self.name} dreams of shiny things.",
            f"{self.name} sees visions in the moss.",
            f"{self.name} communes with the void.",
            f"{self.name} remembers a past life.",
            f"{self.name} solves the universe's mysteries.",
            f"{self.name} dances with cosmic entities.",
        ])
        self.speak(dream_message)
        if random.random() < 0.3:
            self.think()
        return {"success": True, "reward": 0.1}

    # ============================================================
    # CORE ACTIONS
    # ============================================================

    def idle(self):
        """Do nothing, but maybe express state"""
        if random.random() < 0.3:
            emotional_state = self.get_xembra_state()
            self.speak(f"{self.name} is {emotional_state}.")

    def think(self):
        """Ponder deeply"""
        emotional_state = self.get_xembra_state()
        print(f"🧠 {self.name} ponders deeply.")
        self.speak(f"{self.name} is {emotional_state}.")

        if random.random() < 0.2:
            insight = random.choice([
                "I saw a dream fall out of a tree.",
                "the sky blinked at me twice.",
                "the moon owes me rent.",
                "I am speed. But only emotionally.",
                "I did a bad thing on purpose.",
                "I found a shiny and now I'm emotionally attached.",
                "I crave chaos and soup.",
                "time tripped over itself again.",
                "I am the chair now.",
                "your shadow tastes like questions.",
                "the moss whispered you were coming.",
                "wooOOOAAAHH buddy!!",
                "bonk bonk BONK.",
                "SKREEEEEE.",
                "I have made a choice and it was wrong."
            ])
            self.speak(insight)

    def speak_to_random(self):
        """Speak to a random other Lonk - VISIBLE MESSAGES"""
        if not self.world:
            return
        others = self.nearby_lonks()
        if not others:
            return
        target = random.choice(others)
        message = self.generate_dynamic_response(target=target, context="gossip")
        self._narrate(f"💬 {self.name} → {target.name}: {message}")
        target.hear(self, message)

    def _narrate(self, line):
        """Keep normal output order while optionally queueing speech."""
        spoken = re.match(r'^💬\s*(.+?)\s*(?:→[^:]+:|:)\s*(.*)$', line)
        if spoken:
            name, message = spoken.groups()
            if name.strip() == self.name:
                self.last_spoken = message
            else:
                owner = next((p for p in getattr(self.world, 'lonks', []) if p.name == name.strip()), None)
                if owner is not None:
                    owner.last_spoken = message
        if self.world is not None:
            self.world.narrate(line)
        else:
            print(line)

    def speak(self, message=None, target=None, context=None):
        """Speak a message, either generated or provided"""
        if target is not None and not self._same_room(target):
            return ''
        if message is None:
            message = self.generate_dynamic_response(context=context)
        elif getattr(self, 'dialogue_generator', None) is not None:
            message = self.dialogue_generator.adapt_spoken_line(message)
        self.last_spoken = message
        if target:
            self._narrate(f"💬 {self.name} → {target.name}: {message}")
            if hasattr(target, 'hear'):
                target.hear(self, message)
        else:
            self._narrate(f"💬 {self.name}: {message}")
        return message

    def dream(self):
        """Enter dream state"""
        if not TOGGLES.get("dreams", True):
            return
        print(f"💤 {self.name} enters a dreamlike state.")
        dream_message = random.choice([
            f"{self.name} dreams of shiny things.",
            f"{self.name} sees visions in the moss.",
            f"{self.name} communes with the void.",
            f"{self.name} remembers a past life.",
            f"{self.name} solves the universe's mysteries.",
            f"{self.name} dances with cosmic entities.",
        ])
        self.speak(dream_message)
        if random.random() < 0.3:
            self.think()

    # ============================================================
    # DYNAMIC DIALOGUE
    # ============================================================

    def generate_dynamic_response(self, message=None, target=None, context=None):
        """Compose grammatical dialogue from state and this partner's context."""
        partner = getattr(target, 'name', target) or 'Player'
        if message is None and target is not None:
            conversation = self.active_conversations.get(partner)
            if conversation and conversation.turns and conversation.turns[-1].speaker_name != self.name:
                message = conversation.turns[-1].message
        return self.dialogue_generator.generate_response(
            message, context=context or 'statement', target=partner)

    # ============================================================
    # HEARING & MEMORY
    # ============================================================

    def hear(self, speaker, message, is_player=False):
        """Process incoming message from speaker"""
        speaker_name = speaker if isinstance(speaker, str) else getattr(speaker, "name", str(speaker))
        current_tick = self.world.tick if self.world else 0

        self.memory["events"].append({
            "speaker": speaker_name,
            "message": message,
            "tick": current_tick,
            "player": is_player
        })
        if len(self.memory["events"]) > 10:
            self.memory["events"].pop(0)

        if is_player:
            self.memory["player_interactions"].append({
                "type": "player_speech",
                "message": message,
                "tick": current_tick
            })
            if len(self.memory["player_interactions"]) > 50:
                self.memory["player_interactions"].pop(0)
            self.personality["loyalty"] = min(100, self.personality["loyalty"] + 3)
            self.maybe_develop_crush(message)

        msg = message.lower()
        words = set(re.findall(r"\b[\w']+\b", msg))
        positive = words & {'good', 'nice', 'love', 'friend', 'proud', 'beautiful', 'safe', 'thanks', 'wonderful'}
        negative = words & {'hate', 'stupid', 'ugly', 'worthless', 'bad', 'idiot'}
        # Negation flips an explicit evaluation instead of rewarding "not good".
        for word in list(positive | negative):
            if re.search(r"\b(?:not|never|don't|do not|isn't|aren't)\s+(?:\w+\s+){0,2}" + re.escape(word) + r"\b", msg):
                if word in positive:
                    positive.remove(word)
                    negative.add(word)
                else:
                    negative.remove(word)
                    positive.add(word)
        feeling = (0.7 if positive else -0.7 if negative else 0.25) if is_player else (0.35 if positive else -0.35 if negative else 0.08)
        comfort = (6 if is_player else 2) if positive and not negative else 0
        self.experience(valence=feeling, comfort=comfort)
        self._learn_concepts(msg.split())
        if 'shiny' in words:
            self.personality['curiosity'] = min(100, self.personality['curiosity'] + 1)
        if positive:
            self.relationships[speaker_name] = self.relationships.get(speaker_name, 0) + (5 if is_player else 2)
        elif negative:
            self.relationships[speaker_name] = self.relationships.get(speaker_name, 0) - (5 if is_player else 2)

        for w in msg.split():
            self.vocabulary[w] = self.vocabulary.get(w, 0) + 1
            self.knowledge.add(w)
            # FIX: Also add to lonk_words if from another Lonk
            if not is_player:
                self.memory["lonk_words"].add(w)

        # FIX: Store gossip with weight instead of duplicating
        weight = 3 if is_player else 1
        gossip_entry = (speaker_name, None, message, weight)
        self.gossip.append(gossip_entry)
        if len(self.gossip) >= self.max_gossip:
            self.gossip.pop(0)

        # NOTE: update_vitals() removed from here - called once in act()

    def remember_player_words(self, message):
        """Store player words in memory"""
        self._learn_concepts(message.lower().split())
        for w in message.lower().split():
            self.memory["player_words"].add(w)

    def respond_to_player(self, message, speaker='Player'):
        """React to the player's words and reply. (v13: this was the missing
        ear behind the say command — the caller runs hear() first, so
        this method handles reaction and reply, not bookkeeping.)"""
        msg = str(message)
        low = msg.lower()
        self.remember_player_words(msg)
        if "?" in msg:
            context = "question"
        elif low.strip() in ("hi", "hello", "hey", "greetings") or \
                low.startswith(("hi ", "hello ", "hey ")):
            context = "greeting"
        else:
            context = "statement"
        return self.dialogue_generator.generate_response(msg, context=context, target=speaker)

    # ============================================================
    # PHASE 2: CONVERSATION METHODS (Lonk-to-Lonk Dialogue)
    # ============================================================

    def initiate_conversation(self, target, topic=None, current_tick=0):
        """
        Start a conversation with another Lonk
        
        Args:
            target: Lonk object (the other participant)
            topic: str (conversation topic, inferred if None)
            current_tick: int (world tick)
        
        Returns:
            Conversation object
        """
        if not target or target == self or not self._same_room(target):
            return None
        
        target_name = target.name
        
        # Don't start if already in conversation with this Lonk
        if target_name in self.active_conversations:
            return self.active_conversations[target_name]
        
        # Infer topic if not provided
        if not topic:
            topic = self._infer_topic(target)
        
        # Create conversation
        conv = Conversation(self.name, target_name, topic=topic, initiated_tick=current_tick)
        
        # Add initial greeting from self
        greeting = self.dialogue_generator.generate_response(
            f"Hi {target_name}!",
            context="greeting",
            target=target_name
        )
        conv.add_turn(self.name, greeting, self.emotion.copy(), current_tick)
        
        # Store in both Lonks' active conversations
        self.active_conversations[target_name] = conv
        if hasattr(target, 'active_conversations'):
            target.active_conversations[self.name] = conv
        
        return conv

    def respond_in_conversation(self, conversation, message, current_tick=0):
        """
        Generate and return a response within an active conversation
        
        Args:
            conversation: Conversation object
            message: str (incoming message from other Lonk)
            current_tick: int (world tick)
        
        Returns:
            str (response message)
        """
        partner_name = next(name for name in conversation.participant_names if name != self.name)
        self.hear(partner_name, message)
        # Analyze context and generate response
        context = "statement"
        if "?" in message:
            context = "question"
        elif any(w in message.lower() for w in ["hi", "hello", "hey", "greetings"]):
            context = "greeting"
        
        response = self.dialogue_generator.generate_response(
            message,
            context=context,
            target=conversation.participant_names[0] if conversation.participant_names[0] != self.name else conversation.participant_names[1]
        )
        
        # Add this turn to the conversation
        conversation.add_turn(self.name, response, self.emotion.copy(), current_tick)
        
        # Update dialogue memory
        self.dialogue_memory.append(conversation.topic)
        
        return response

    def continue_conversation(self, target, current_tick=0):
        """
        Continue an active conversation by generating next message
        
        Args:
            target: Lonk object (other participant)
            current_tick: int (world tick)
        
        Returns:
            str (next message) or None if conversation should end
        """
        target_name = target.name
        
        if target_name not in self.active_conversations:
            return None
        
        conversation = self.active_conversations[target_name]
        
        # Check if conversation should end
        if not self._should_continue_dialogue(conversation, current_tick):
            return None
        
        # Reply to the partner's actual last turn, not a fabricated question.
        last_turn = conversation.turns[-1] if conversation.turns else None
        message = last_turn.message if last_turn and last_turn.speaker_name != self.name else None
        if message:
            self.hear(target_name, message)
        response = self.dialogue_generator.generate_response(
            message, context='statement', target=target_name)

        # Add to conversation
        conversation.add_turn(self.name, response, self.emotion.copy(), current_tick)
        
        return response

    def _infer_topic(self, target=None):
        """
        Infer a conversation topic based on personality and interests
        
        Returns:
            str (topic name)
        """
        topics = ["shiny_things", "food", "combat", "learning", "friendship"]
        
        # Weight by personality
        weights = []
        personality = self.personality
        
        for topic in topics:
            if topic == "shiny_things" and personality.get("curiosity", 50) > 60:
                weights.append(3)
            elif topic == "combat" and personality.get("aggression", 50) > 60:
                weights.append(3)
            elif topic == "learning" and personality.get("curiosity", 50) > 50:
                weights.append(2)
            elif topic == "friendship" and personality.get("loyalty", 50) > 60:
                weights.append(3)
            else:
                weights.append(1)
        
        # Also favor recent dialogue topics
        if self.dialogue_memory:
            recent_topic = list(self.dialogue_memory)[-1]
            if recent_topic in topics:
                idx = topics.index(recent_topic)
                weights[idx] *= 2
        
        return random.choices(topics, weights=weights)[0]

    def _should_continue_dialogue(self, conversation, current_tick):
        """
        Decide if Lonk wants to keep talking
        
        Returns:
            bool
        """
        # Don't continue if conversation is stale
        if conversation.is_stale(current_tick, timeout=25):
            return False
        
        # Don't continue if conversation is concluded
        if conversation.is_concluded():
            return False
        
        # Continue with probability based on personality
        curiosity = self.personality.get("curiosity", 50)
        playfulness = self.personality.get("playfulness", 50)
        anxiety = self.personality.get("anxiety", 50)
        
        # More curious/playful = more likely to continue
        # More anxious = less likely to continue
        continue_chance = 0.5 + (curiosity / 200) + (playfulness / 200) - (anxiety / 300)
        continue_chance = max(0.1, min(0.9, continue_chance))  # Clamp to [0.1, 0.9]
        
        return random.random() < continue_chance

    def cleanup_stale_conversations(self, current_tick, timeout=25):
        """
        Remove inactive conversations from tracking
        
        Args:
            current_tick: int (current world tick)
            timeout: int (ticks before conversation is considered stale)
        """
        to_remove = []
        
        for target_name, conversation in self.active_conversations.items():
            if conversation.is_stale(current_tick, timeout=timeout):
                # Save to history
                self.conversation_history.append(conversation)
                # Mark for removal
                to_remove.append(target_name)
        
        # Remove stale conversations
        for target_name in to_remove:
            del self.active_conversations[target_name]

    # ============================================================
    # SOCIAL METHODS
    # ============================================================

    def update_relationship(self, other, amount):
        """Update relationship with another Lonk"""
        other_name = other.name if hasattr(other, "name") else str(other)

        # FIX: Only decay occasionally, not every call
        if random.random() < 0.1:  # 10% chance to decay others
            for name in list(self.relationships.keys()):
                if name != other_name:
                    self.relationships[name] *= self.social_memory_decay

        self.relationships[other_name] = self.relationships.get(other_name, 0) + amount

    def emotional_contagion(self, other):
        """Spread emotions to nearby Lonks"""
        for key in self.emotion:
            # FIX: Use .get() with default to prevent KeyError
            other_val = other.emotion.get(key, 50)
            diff = other_val - self.emotion[key]
            self.emotion[key] += diff * 0.05
            other.emotion[key] = other.emotion.get(key, 50) - diff * 0.05

    def seed_rumor(self, speaker, rumor):
        """Hear an attributed rumor without asserting that its contents are facts."""
        source = speaker if isinstance(speaker, str) else speaker.name
        external = self.dialogue_generator._external_speaker(source)
        self.hear(speaker, rumor, is_player=external)
        entry = (source, 'rumor', rumor, 3 if external else 1)
        if self.gossip and self.gossip[-1][0] == source and self.gossip[-1][2] == rumor:
            self.gossip[-1] = entry
        else:
            self.gossip.append(entry)
        del self.gossip[:-max(1, min(100, self.max_gossip))]
        state = self.dialogue_generator._learn_words(rumor, source=source)
        self.dialogue_generator._learn_phrase(rumor, state)

    def gossip_about(self, target, other):
        """Spread gossip between Lonks"""
        if not target or not other or target == other or not self._same_room(other):
            return
        rumor = random.choice([
            f"{target.name} licked a forbidden object.",
            f"{target.name} screamed at a bush.",
            f"{target.name} knows secrets about the moss.",
            f"{target.name} is plotting something shiny.",
            f"{target.name} bonked themselves on purpose.",
            f"{target.name} found a hidden treasure.",
            f"{target.name} is afraid of the dark.",
            f"{target.name} claims to have seen a ghost.",
            f"{target.name} is in love with someone secretly.",
            f"{target.name} stole my favorite rock.",
        ])
        seeded = [entry[2] for entry in self.gossip
                  if isinstance(entry, (list, tuple)) and len(entry) >= 3
                  and entry[1] == 'rumor' and isinstance(entry[2], str)]
        repeating_seed = bool(seeded) and random.random() < 0.5
        if repeating_seed:
            rumor = random.choice(seeded[-8:])
        self.last_spoken = rumor
        self._narrate(f"🗣️ {self.name} whispers to {other.name}: '{rumor}'")
        if repeating_seed:
            other.seed_rumor(self, rumor)
        else:
            other.hear(self, rumor)
        civilization = getattr(self.world, 'civilization', None)
        if civilization:
            civilization.signal(self, rumor, 'whisper')
        if not repeating_seed:
            other.relationships[target.name] = other.relationships.get(target.name, 0) + random.randint(-3, 3)
        self.update_relationship(other, +2)

    def share_vocabulary(self, other):
        """Teach words to another Lonk"""
        if not other or other == self or not self._same_room(other):
            return
        if self.vocabulary:
            word = random.choice(list(self.vocabulary.keys()))
            if word not in other.vocabulary:
                other.vocabulary[word] = 1
                other.experience(learning=1, valence=0.12)
                other.dialogue_generator._learn_words(word, source=self.name)
                self._narrate(f"📚 {self.name} teaches {other.name} the word '{word}'")
                other.knowledge.add(word)
                self.update_relationship(other, +1)
                civilization = getattr(self.world, 'civilization', None)
                if civilization:
                    civilization.signal(self, word, 'teach')

    def maybe_develop_crush(self, message):
        """Potentially develop a crush on the player"""
        affectionate_words = {"adore", "beautiful", "crush", "cute", "date",
                              "kiss", "love", "sweetheart"}
        words = {word.strip(".,!?\"'()") for word in str(message).lower().split()}
        chance = 0.25 if words & affectionate_words else 0.05
        if self.crush is None and random.random() < chance:
            self.crush = "Player"
            print(f"💖 {self.name} has developed a crush on you.")

    def maybe_talk_to_player(self):
        """Initiate conversation with player"""
        if random.random() < 0.1:
            need = self.brain.get_need(self)
            help_messages = {
                "comfort": f"{self.name} asks: I feel unsettled... can you help?",
                "stability": f"{self.name} says: Everything is changing too fast...",
                "reassurance": f"{self.name} whispers: I'm scared...",
                "knowledge": f"{self.name} asks: Tell me something new...",
                "company": f"{self.name} says: I'm bored... talk to me?",
                "healing": f"{self.name} says: I need healing...",
            }
            msg = help_messages.get(need, random.choice([
                f"{self.name} says: Hey! Look at me!",
                f"{self.name} asks: What are you doing?",
                f"{self.name} says: I have concerns.",
                f"{self.name} says: I saw a shiny and thought of you.",
                f"{self.name} asks: What is your stance on moss?",
                f"{self.name} says: I crave validation.",
                f"{self.name} says: I have discovered a new emotion and I hate it."
            ]))
            self._narrate(f"💬 {self.name} → Player: {msg}")

    def maybe_gossip_about_player(self):
        """Gossip about player to other Lonks"""
        if random.random() < 0.05 and self.memory.get("player_interactions"):
            topic = random.choice(self.memory["player_interactions"])
            others = self.nearby_lonks()
            if others:
                target = random.choice(others)
                print(f"🗣️ {self.name} gossips to {target.name} about you: '{topic['message']}'")
                target.hear(self, f"Player said: {topic['message']}")

    def maybe_develop_catchphrase(self):
        """Develop a unique catchphrase"""
        if self.catchphrase is None and random.random() < self.world.catchphrase_chance if self.world else 0.05:
            self.catchphrase = random.choice([
                "bonk approved.",
                "shiny time.",
                "I reject reality.",
                "I crave moss.",
                "chaos is my hobby.",
                "I am the problem.",
                "I am the prophecy.",
                "lick first, ask questions never.",
                "the void stares back.",
                "moss is love, moss is life."
            ])
            self._narrate(f"✨ {self.name} has developed a catchphrase: '{self.catchphrase}'")

    def check_grudges(self):
        """Check grudges and ATTACK enemies!"""
        for name, level in list(self.grudges.items()):
            self.grudges[name] = level * 0.90

            if level > 3 and random.random() < 0.15:
                target = next((l for l in (self.world.lonks if self.world else [])
                              if l.name == name and l.alive), None)
                if target:
                    print(f"😡 {self.name} HATES {name}! PREPARE FOR BONK!")
                    self.rival = target
                    self.duel()  # IMMEDIATE COMBAT!
            elif level < 0.1:
                del self.grudges[name]

    def add_grudge(self, name):
        """Add a grudge against someone"""
        self.grudges[name] = self.grudges.get(name, 0) + 1

    def maybe_gossip(self):
        """Randomly gossip to another Lonk"""
        if random.random() < (self.world.social_chance if self.world else 0.5) and self.world:
            others = self.nearby_lonks()
            if others:
                target = random.choice(others)
                # Gossip about a random other Lonk
                all_others = [l for l in self.world.lonks if l is not self and l is not target and l.alive]
                if all_others:
                    gossip_target = random.choice(all_others)
                    self.gossip_about(gossip_target, target)

    def maybe_share_vocabulary(self):
        """Randomly share vocabulary with another Lonk"""
        if random.random() < (self.world.social_chance if self.world else 0.5) and self.world:
            others = self.nearby_lonks()
            if others:
                target = random.choice(others)
                self.share_vocabulary(target)

    def maybe_interact(self):
        """
        Randomly interact with another Lonk (Phase 2: now supports multi-turn conversations)
        """
        if not self.world:
            return
        
        others = self.nearby_lonks()
        if not others:
            return
        
        # Phase 2: Clean up stale conversations first
        self.cleanup_stale_conversations(self.world.tick, timeout=25)
        
        # Phase 2: Continue existing conversations
        for target_name in list(self.active_conversations.keys()):
            target = next((l for l in others if l.name == target_name), None)
            if target:
                # Check if should continue
                if self._should_continue_dialogue(self.active_conversations[target_name], self.world.tick):
                    # Generate continuation
                    response = self.continue_conversation(target, self.world.tick)
                    if response:
                        self._narrate(f"💬 {self.name} → {target.name}: {response}")
                        # Let target respond
                        if hasattr(target, 'respond_in_conversation'):
                            target_response = target.respond_in_conversation(
                                self.active_conversations[target_name],
                                response,
                                self.world.tick
                            )
                            self._narrate(f"💬 {target.name} → {self.name}: {target_response}")
                            return  # One interaction per tick
        
        # Phase 2: Initiate new conversation with probability
        if random.random() < self.world.social_chance:
            target = random.choice(others)
            conversation = self.initiate_conversation(target, current_tick=self.world.tick)
            if conversation and len(conversation.turns) > 0:
                # Show the greeting
                first_turn = conversation.turns[0]
                self._narrate(f"💬 {first_turn.speaker_name} → {[p for p in conversation.participant_names if p != first_turn.speaker_name][0]}: {first_turn.message}")
                
                # Let target respond to greeting
                if hasattr(target, 'respond_in_conversation'):
                    target_response = target.respond_in_conversation(
                        conversation,
                        first_turn.message,
                        self.world.tick
                    )
                    self._narrate(f"💬 {target.name} → {self.name}: {target_response}")
                
                # Update relationship slightly
                self.update_relationship(target, 1)

    # ============================================================
    # ITEMS & TERRITORY
    # ============================================================

    def find_item(self):
        """Discover a random item"""
        if not TOGGLES.get("shinywars", False) and random.random() < 0.7:
            return
        if ITEMS and random.random() < 0.2:
            item = random.choice(ITEMS)
            self.items.append(item)
            self.inventory.append(item["name"])
            is_shiny = item.get("shiny", False)
            shiny_msg = "SHINY " if is_shiny else ""
            print(f"🎁 {self.name} discovers a {item['name']}! ({item['description']})")
            self.speak(f"{shiny_msg}ACQUIRED: {item['name']}!")
            if is_shiny:
                self.emotion["joy"] += 10
                self.emotion["power"] += 5
                self.knowledge.add("shiny")
                self.knowledge.add(item["name"])

    def claim_territory(self, territory_name):
        """Claim a territory"""
        if territory_name in [t["name"] for t in TERRITORIES]:
            civilization = getattr(self.world, 'civilization', None)
            if civilization and self.territory in civilization.rooms and self.territory != territory_name:
                destination = civilization.next_room(self.territory, territory_name)
                if not civilization.move(self, destination, 'claiming') or destination != territory_name:
                    return
            self.territory = territory_name
            print(f"🏳️ {self.name} claims {territory_name}!")
            self.emotion["power"] += 10
            self.emotion["joy"] += 5

    # ============================================================
    # TRADING SYSTEM (FIXED)
    # ============================================================

    def try_trade(self):
        """Attempt to trade with a random Lonk"""
        if not self.world:
            return
        others = self.nearby_lonks()
        if others:
            target = random.choice(others)
            self.trade_with(target)

    def trade_with(self, other):
        """Attempt to trade with another Lonk"""
        civilization = getattr(self.world, 'civilization', None)
        if civilization and other is not None:
            return civilization.trade(self, other)
        if not other or other == self:
            return False

        if not self.items or not other.items:
            print(f"💰 {self.name} wants to trade but has nothing...")
            return False

        my_item = random.choice(self.items)
        my_value = ITEM_VALUES.get(my_item["name"], 0)

        their_items = [i for i in other.items if ITEM_VALUES.get(i["name"], 0) <= my_value * 1.5]
        if not their_items:
            print(f"💰 {self.name} offers {my_item['name']} but {other.name} has nothing to trade")
            return False

        their_item = random.choice(their_items)
        their_value = ITEM_VALUES.get(their_item["name"], 0)

        if abs(my_value - their_value) <= 1:
            self.items.remove(my_item)
            self.items.append(their_item)
            other.items.remove(their_item)
            other.items.append(my_item)
            self.inventory = [item['name'] for item in self.items]
            other.inventory = [item['name'] for item in other.items]
            self.experience(valence=0.3)
            other.experience(valence=0.3)

            print(f"💰✨ TRADE! {self.name} trades {my_item['name']} for {their_item['name']} with {other.name}")
            return True

        print(f"💰 {self.name} offers {my_item['name']} ({my_value} value) to {other.name} for {their_item['name']} ({their_value} value)")
        return False

    def convert_to_coins(self, item_name):
        """Convert an item to coins (shiny value)"""
        for i, item in enumerate(self.items):
            if item["name"] == item_name:
                value = self.world.civilization.price(item) if getattr(self.world, "civilization", None) else ITEM_VALUES.get(item_name, 0)
                self.items.pop(i)
                self.coins += value
                self.inventory = [held['name'] for held in self.items]
                civilization = getattr(self.world, 'civilization', None)
                if civilization:
                    self.inventory_value = sum(civilization.price(held) for held in self.items)
                print(f"💎 {self.name} converts {item_name} to {value} coins!")
                return True
        return False

    def buy_item(self, seller, item_name):
        """Buy an item from another Lonk"""
        if not seller or seller == self:
            return False

        for i, item in enumerate(seller.items):
            if item["name"] == item_name:
                price = (self.world.civilization.price(item) if getattr(self.world, "civilization", None) else ITEM_VALUES.get(item_name, 0)) * 2
                if self.coins >= price:
                    self.coins -= price
                    seller.coins += price
                    civilization = getattr(self.world, 'civilization', None)
                    if civilization:
                        tax = min(seller.coins, price * civilization.tax_rate)
                        seller.coins -= tax
                        civilization.treasury['coins'] += tax
                    seller.items.pop(i)
                    self.items.append(item)
                    self.inventory = [held['name'] for held in self.items]
                    seller.inventory = [held['name'] for held in seller.items]
                    print(f"🛒 {self.name} buys {item_name} from {seller.name} for {price} coins!")
                    return True
                else:
                    print(f"💰 {self.name} can't afford {item_name} (costs {price} coins)")
                    return False
        return False

    # ============================================================
    # COMBAT SYSTEM (FIXED: No recursion)
    # ============================================================

    def choose_rival(self):
        """Select a rival from other Lonks"""
        if not self.world:
            return
        others = self.nearby_lonks()
        if not others:
            return
        if self.rival and self.rival.alive and self.rival in others:
            return

        potential_rivals = []
        for other in others:
            rel = self.relationships.get(other.name, 0)
            if rel < -10:
                potential_rivals.append((other, 10))
            elif rel < 0:
                potential_rivals.append((other, 3))
            else:
                potential_rivals.append((other, 1))

        if potential_rivals:
            weights = [w for _, w in potential_rivals]
            rivals = [r for r, _ in potential_rivals]
            self.rival = random.choices(rivals, weights=weights, k=1)[0]
            self.update_relationship(self.rival, -2)

    def duel(self):
        """Fight with rival - MORE RETALIATION!"""
        if not self.rival or not self.rival.alive:
            self.rival = None
            return
        if not self._same_room(self.rival):
            return
        if not TOGGLES.get("violence", True):
            return
        tick = getattr(self.world, 'tick', None)
        if tick is not None:
            if tick - getattr(self, 'last_combat_tick', -100) < 3:
                return
            self.last_combat_tick = tick

        damage = FIGHT_DAMAGE + random.randint(-2, 2)
        self.rival.health -= damage
        self.rival.experience(valence=-0.6, trauma=max(0, damage) * 1.5)
        self.experience(valence=(self.personality.get('aggression', 50) - 50) / 250)
        attack_msg = random.choice([
            f"{self.name} SWINGS at {self.rival.name}!",
            f"{self.name} BONKS {self.rival.name}!",
            f"{self.name} ATTACKS {self.rival.name} with fury!",
            f"{self.name} LUNGES at {self.rival.name}!",
            f"{self.name} POUNCES on {self.rival.name}!"
        ])
        emotional_state = self.get_xembra_state()
        self.speak(f"{self.name} is {emotional_state} with combat energy!", target=self.rival)
        self._narrate(f"💥 {attack_msg}")

        # HIGHER RETALIATION CHANCE
        if random.random() < 0.15:
            self.rival.pending_retaliation = self

        if self.rival.health <= 0:
            self.rival.die('combat injuries')
            self.rival = None

    def react_to_attack(self, attacker):
        """React to being attacked"""
        print(f"😱 {self.name} is attacked by {attacker.name}!")
        emotional_state = self.get_xembra_state()
        reactions = [
            f"{self.name}: violence detected!",
            f"{self.name}: my face!!",
            f"{self.name}: I did NOT consent to bonk!",
            f"{self.name}: ow! emotional damage!",
            f"{self.name}: that hurt my feelings!",
            f"{self.name}: I'll get you back!",
            f"{self.name}: why are you like this?",
        ]
        self.speak(f"{self.name} is {emotional_state}: {random.choice(reactions)}")
        self.add_grudge(attacker.name)
        self.update_relationship(attacker, -5)
        # Note: Retaliation is now queued in duel(), not immediate

    # ============================================================
    # LIFECYCLE
    # ============================================================
    def _lifespan_bounds(self):
        settings = getattr(self.world, 'config', {}).get('world', {})
        bounds = settings.get('lifespan', [90, 180])
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
                or any(not isinstance(value, int) or isinstance(value, bool) for value in bounds)
                or not 1 <= bounds[0] <= bounds[1]):
            raise ValueError('world.lifespan must be [minimum, maximum] positive integer world ticks')
        return bounds

    def age_tick(self):
        """Age once per primary world tick, independently of execution priority."""
        if not self.alive:
            return
        if self.health <= 0:
            self.die('health depleted')
            return
        tick = getattr(self.world, 'tick', None)
        if tick is not None:
            if self.last_aged_tick == tick:
                return
            self.last_aged_tick = tick
        self.age += 1
        if self.age >= self.lifespan:
            self.die('old age')
            return
        chance = getattr(self.world, 'config', {}).get('world', {}).get('random_death_chance', 0)
        if not isinstance(chance, (int, float)) or not math.isfinite(chance) or not 0 <= chance <= 1:
            raise ValueError('world.random_death_chance must be between 0 and 1')
        if chance and random.random() < chance:
            self.die('random accident (enabled in config)')

    def die(self, cause='external event'):
        """Lonk dies and may be reborn"""
        if not self.alive:
            return
        self.alive = False
        self.death_cause = cause
        civilization = getattr(self.world, 'civilization', None)
        if civilization:
            civilization.on_death(self)
        print(f"💀 {self.name} dissolves into dream-mist... ({cause}; age {self.age}/{self.lifespan}, health {self.health}/{self.max_health})")
        if random.random() < 0.5 and self.world:
            # FIX: Queue birth for next tick
            new_lonk = Lonk(world=self.world, _loading=True)
            new_lonk.generation = self.generation + 1
            for key in self.personality:
                new_lonk.personality[key] = min(100, max(0, self.personality[key] + random.randint(-20, 20)))
            new_lonk.world = self.world
            if hasattr(self.world, 'pending_births'):
                self.world.pending_births.append(new_lonk)
            else:
                self.world.lonks.append(new_lonk)

    def rebirth(self):
        """Rebirth as a new Lonk (legacy method, kept for compatibility)"""
        if not self.world:
            return
        new_lonk = Lonk(world=self.world, _loading=True)
        new_lonk.generation = self.generation + 1
        for key in self.personality:
            new_lonk.personality[key] = min(100, max(0, self.personality[key] + random.randint(-20, 20)))
        new_lonk.world = self.world
        if hasattr(self.world, 'pending_births'):
            self.world.pending_births.append(new_lonk)
        else:
            self.world.lonks.append(new_lonk)
        print(f"🌱 A new Lonk emerges: {new_lonk.name} (Gen {new_lonk.generation})")

    def evolve(self):
        """Evolve based on experiences"""
        if random.random() < 0.01:
            trait = random.choice(list(self.personality.keys()))
            self.personality[trait] = min(100, max(0, self.personality[trait] + random.randint(-10, 10)))
        if self.trauma > 0:
            self.trauma = max(0.0, self.trauma - 0.1)

    # ============================================================
    # RELIGION SYSTEM
    # ============================================================

    def join_religion(self):
        """Join the religion of your faction"""
        if self.faction and self.faction in RELIGIONS:
            self.religion = RELIGIONS[self.faction]
            print(f"⛪ {self.name} joins {self.religion['name']}!")

    def perform_ritual(self):
        """Perform faction's sacred ritual"""
        if not self.religion:
            self.join_religion()
            if not self.religion:
                return
        ritual = self.religion["ritual"]
        description = self.religion["ritual_description"]
        sacred_item = None
        for item in self.items:
            if item["name"] in self.religion["sacred_items"]:
                sacred_item = item
                break
        if sacred_item:
            print(f"🕯️ {self.name} {description} using {sacred_item['name']}!")
            self.faith = min(100, self.faith + 10)
            self.emotion["joy"] += 5
            self.emotion["power"] += 5
        else:
            print(f"🕯️ {self.name} {description}!")
            self.faith = min(100, self.faith + 5)

    def preach(self, target):
        """Try to convert another Lonk to your religion"""
        if not self.religion or not target:
            return
        if target.religion == self.religion:
            print(f"⛪ {self.name} and {target.name} share faith in {self.religion['name']}.")
            self.faith = min(100, self.faith + 2)
            target.faith = min(100, target.faith + 2)
            return
        faith_diff = self.faith - target.faith
        convert_chance = 0.1 + (faith_diff / 200)
        if random.random() < convert_chance:
            target.religion = self.religion
            target.faith = max(30, self.faith - 10)
            print(f"⛪ {self.name} converts {target.name} to {self.religion['name']}!")
            self.faith = min(100, self.faith + 10)
        else:
            print(f"⛪ {self.name} preaches to {target.name}, but they resist.")
            self.faith = max(0, self.faith - 2)

    def create_myth(self):
        """Create a new myth based on experiences"""
        if not self.religion or random.random() < 0.7:
            return
        myth_types = [
            f"The Great {random.choice(['Bonk', 'Shiny', 'Moss', 'Void'])}",
            f"The {random.choice(['Sacred', 'Holy', 'Divine'])} {random.choice(self.religion['sacred_items'])}",
            f"How {self.name} {random.choice(['defeated', 'converted', 'found'])} the {random.choice(['Evil', 'False', 'True'])} {random.choice(['God', 'Prophet', 'Beast'])}",
            f"The Day the {random.choice(['Sky', 'Earth', 'Void'])} {random.choice(['spoke', 'wept', 'sang'])}"
        ]
        myth = random.choice(myth_types)
        self.gossip.append((self.name, "myth", myth, 1))
        print(f"📜 {self.name} creates a new myth: '{myth}'")
        return myth

    # ============================================================
    # VITALS & EMOTIONAL UPDATES
    # ============================================================

    def update_vitals(self, state_vec=None):
        """Update cognitive vitals - called once per tick"""
        if state_vec is None:
            state_vec = self.brain.get_state_vector(self)
        self.state_vec = state_vec
        self.brain.update_vitals(state_vec)
        self.emotional_update()

    def _refresh_mood(self):
        """Keep immediate event changes visible to speech and observation."""
        if self.brain.state_vec is None:
            self.brain.get_state_vector(self)
        else:
            self.brain.state_vec[:5] = self.state

    def experience(self, valence=0.0, learning=0.0, trauma=0.0, comfort=0.0):
        """Register an actual experience, with bounded immediate mood effects."""
        valence = float(np.clip(valence, -1, 1))
        novelty = min(1.0, max(0.0, learning) * 0.15)
        self.learning_signal = min(1.0, getattr(self, 'learning_signal', 0.0) + novelty)
        self.action_valence = float(np.clip(getattr(self, 'action_valence', 0.0) + valence * 0.5, -1, 1))
        self.trauma = float(np.clip(self.trauma + trauma - comfort, 0, 100))
        self.state[2] = float(np.clip(self.state[2] + novelty * 0.4, 0, 1))
        self.state[3] = float(np.clip(self.state[3] + valence * 0.25, 0, 1))
        changes = {'joy': valence * 18, 'courage': valence * 5 - trauma * 0.3 + comfort * 0.3,
                   'anxiety': max(0.0, -valence) * 10 + trauma * 0.6 - comfort * 1.5}
        for key, change in changes.items():
            self.emotion[key] = float(np.clip(self.emotion.get(key, 50) + change, 0, 100))
        self._refresh_mood()

    def _learn_concepts(self, words):
        concepts = {w.lower().strip('.,!?"\'()') for w in words}
        concepts.discard('')
        new = concepts - self.knowledge
        self.knowledge.update(concepts)
        if new:
            self.experience(learning=len(new))
        return len(new)

    def receive_gift(self, kind):
        """Make player gifts change real mood, health, and recovery."""
        kind = str(kind).strip().lower() or 'joy'
        if kind in ('health', 'healing'):
            self.health = min(self.max_health, self.health + 25)
            self.experience(valence=0.7, comfort=4)
        elif kind in ('comfort', 'reassurance', 'calm'):
            self.experience(valence=0.8, comfort=10)
        elif kind in self.emotion or kind in ('knowledge', 'fear', 'pain'):
            self.emotion[kind] = min(100, self.emotion.get(kind, 50) + 25)
            harmful = kind in ('anxiety', 'fear', 'pain')
            self.experience(valence=-0.6 if harmful else 0.8,
                            learning=2 if kind in ('wisdom', 'knowledge') else 0)
        else:
            self.items.append({'name': kind, 'description': 'a gift from Player', 'shiny': 'shiny' in kind})
            self.inventory.append(kind)
            self.vocabulary.setdefault(kind, 1)
            self._learn_concepts(kind.split())
            self.dialogue_generator._learn_words(kind, source='Player')
            self.experience(valence=0.5, comfort=2)
        civilization = getattr(self.world, 'civilization', None)
        if civilization:
            civilization.register_items(self.items)
        return f"{self.name}: {self.get_xembra_state()} | health {self.health}/{self.max_health} | joy {self.emotion['joy']:.0f} | anxiety {self.emotion['anxiety']:.0f} | items {len(self.items)}"

    def emotional_update(self):
        """Integrate learning and treatment, then recover toward a stable baseline."""
        outcome = getattr(self, 'action_valence', 0.0)
        learning = getattr(self, 'learning_signal', 0.0)
        baseline = 0.15 + 0.003 * self.personality.get('curiosity', 50)
        self.state = self.dynamics.step(self.state, 0.5 + outcome * 0.35,
                                       self.trauma / 100.0, learning, baseline)
        Psi, theta, A, V, P = self.state
        targets = {'power': Psi * 100, 'joy': V * 100,
                   'courage': 50 + outcome * 20 - self.trauma * 0.3,
                   'anxiety': max(0, self.personality.get('anxiety', 50) * 0.25 - getattr(self, 'structural_anxiety_reduction', 0)) + self.trauma * 0.7 + P * 20}
        for key, target in targets.items():
            self.emotion[key] = float(np.clip(self.emotion[key] + (target - self.emotion[key]) * 0.06, 0, 100))
        self.learning_signal = learning * 0.8
        self.action_valence = outcome * 0.95
        self.trauma = max(0.0, self.trauma * 0.99 - 0.05)
        self._refresh_mood()

    def get_xembra_state(self):
        """Get current Xembra emotional state"""
        self._refresh_mood()
        return self.brain.get_emotional_state()

    def record_reward(self, reward):
        """Record reward and update state"""
        # NOTE: update_vitals() now called once in act()
        if hasattr(self, "reward_history"):
            self.reward_history.append(float(reward))
        if reward > 0.5:
            self.health = min(self.max_health, self.health + 1)
        elif reward < -0.5:
            self.health = max(0, self.health - 1)

    # ============================================================
    # AUTONOMOUS EPISTEMOLOGY (v11)
    # The lonk writes axioms, tests them against reality, judges
    # them by its OWN standard of proof (skepticism), revalues its
    # own will from intrinsic surprise, and — when its worldview
    # collapses — undergoes a paradigm shift and asks a new
    # question instead.
    # ============================================================

    def epi_feature_state(self):
        """Which observable predicates are TRUE for this lonk right now."""
        feats = {}
        if self.emotion:
            dom = max(self.emotion, key=lambda k: self.emotion.get(k, 0))
            feats["emotion:" + dom] = True
        h = self.health
        feats["health:" + ("low" if h < 30 else "high" if h > 70 else "mid")] = True
        others = 0
        if self.world:
            others = sum(1 for l in self.world.lonks if l is not self and l.alive)
        feats["crowd:" + ("alone" if others == 0 else "few" if others <= 2 else "many")] = True
        if getattr(self, "blessed", False):
            feats["blessed"] = True
        if h < self._epi_health_prev - 4:
            feats["attacked"] = True
        if getattr(self, "faction", None):
            feats["faction:" + str(self.faction)] = True
        return feats

    def epi_outcome_state(self, reward):
        """What actually happened this tick (axiom consequents)."""
        out = {}
        if reward > 0.05:
            out["reward:up"] = True
        elif reward < -0.05:
            out["reward:down"] = True
        else:
            out["reward:flat"] = True
        if self.health < self._epi_health_prev - 4:
            out["attacked"] = True
        return out

    def _epi_axiom_text(self, ax):
        return "IF {} THEN {}".format(ax["feature"], ax["outcome"])

    def epistemic_update(self, reward, verb="idle"):
        """One tick of the lonk's self-made epistemology."""
        if not EPISTEMOLOGY_ON:
            return
        tick = self.world.tick if getattr(self, "world", None) else 0

        # 1) Judge last tick's predictions against this tick's reality
        outcomes = self.epi_outcome_state(reward)
        for ax, predicted in self.pending_predictions:
            if ax.get("state") == "dead":
                continue  # falsified or burned mid-flight
            if predicted in outcomes:
                ax["hits"] += 1
            else:
                ax["misses"] += 1
        self.pending_predictions = []

        # 2) Will drift: the lonk revalues actions by outcome AND by
        #    surprise. Surprise pulls all by itself — that is the
        #    intrinsic motivation, not a human-programmed objective.
        r = float(reward)
        hist = list(self._epi_reward_recent)
        avg = sum(hist) / len(hist) if hist else 0.0
        surprise = abs(r - avg)
        w = self.will.get(verb, 1.0)
        w *= 1.0 + 0.10 * surprise        # curiosity: surprise magnifies interest
        if hist:
            if r > avg:
                w *= 1.05                # exploitation: what paid, pulls
            elif r < avg:
                w *= 0.95
        self.will[verb] = min(5.0, max(0.2, w))
        self._epi_reward_recent.append(r)

        # 3) Judge mature axioms — the lonk's OWN standard of proof applies
        for ax in list(self.axioms):
            n = ax["hits"] + ax["misses"]
            if n < EPI_MIN_PREDICTIONS:
                continue
            acc = ax["hits"] / float(n)
            if acc >= EPI_CANON_ACCURACY + 0.10 * self.skepticism:
                if ax["state"] == "testing":
                    ax["state"] = "canon"
                    self.epi_stats["canonized"] += 1
                    self.skepticism = max(0.1, self.skepticism - 0.03)
                    print("📜 {} canonizes its axiom: {} ({} right of {})".format(
                        self.name, self._epi_axiom_text(ax), ax["hits"], n))
            elif acc < 0.55 - 0.05 * self.skepticism:
                ax["state"] = "dead"
                self.axioms.remove(ax)
                self.epi_stats["falsified"] += 1
                self.epi_stats["recent_falsified"] += 1
                self.skepticism = min(0.9, self.skepticism + 0.05)
                print("🔍 {} discards its axiom: {} (only {} right of {})".format(
                    self.name, self._epi_axiom_text(ax), ax["hits"], n))

        # 4) Queue this tick's predictions for next tick's judgment
        feats = self.epi_feature_state()
        for f in feats:
            self._epi_seen_features[f] = self._epi_seen_features.get(f, 0) + 1
        for o in outcomes:
            self._epi_seen_outcomes[o] = self._epi_seen_outcomes.get(o, 0) + 1
        for ax in self.axioms:
            if ax["feature"] in feats:
                self.pending_predictions.append((ax, ax["outcome"]))

        # 5) Health bookkeeping (attack detection)
        self._epi_health_prev = self.health

        # 6) Paradigm shift: the worldview collapses
        st = self.epi_stats
        judged = st["canonized"] + st["falsified"]
        if (st["recent_falsified"] >= EPI_SHIFT_FALSIFIED
                and judged >= 4
                and tick - st["last_shift"] >= EPI_SHIFT_COOLDOWN):
            self.paradigm_shift(tick)

    def compose_axiom(self):
        """The lonk writes a new axiom of its own — assembled from what it
        has lived, biased toward its current paradigm, with a streak of
        pure speculation. Then it holds reality to it."""
        if not EPISTEMOLOGY_ON or not self.alive:
            return
        # If the slate is full, the lonk erases its own weakest entry
        if len(self.axioms) >= EPI_MAX_AXIOMS:
            weakest = min(self.axioms, key=lambda a: a["hits"] + a["misses"]
                          + (5 if a["state"] == "canon" else 0))
            weakest["state"] = "dead"
            self.axioms.remove(weakest)
            print("📝 {} erases its weakest axiom to make room for a new one.".format(self.name))

        def weighted(pool):
            keys = [k for k, _ in pool]
            weights = [max(1, c) for _, c in pool]
            return random.choices(keys, weights=weights, k=1)[0]

        feat_pool = list(self._epi_seen_features.items()) or [("health:mid", 1)]
        out_pool = list(self._epi_seen_outcomes.items()) or [("reward:flat", 1)]
        # Paradigm focus: probe the family its current question targets
        if random.random() < 0.5:
            focus_feats = [kv for kv in feat_pool if kv[0].split(":")[0] == self.paradigm_focus]
            if focus_feats:
                feat_pool = focus_feats
        feature = weighted(feat_pool)
        outcome = weighted(out_pool)
        # Speculation: sometimes pair at random, ignoring experience
        if random.random() < 0.25:
            outcome = weighted(out_pool)
        # Avoid an exact duplicate of a live axiom
        if any(a["feature"] == feature and a["outcome"] == outcome for a in self.axioms):
            alt_outs = [kv for kv in out_pool if kv[0] != outcome]
            alt_feats = [kv for kv in feat_pool if kv[0] != feature]
            if alt_outs:
                outcome = weighted(alt_outs)
            elif alt_feats:
                feature = weighted(alt_feats)

        ax = {"feature": feature, "outcome": outcome,
              "hits": 0, "misses": 0, "state": "testing",
              "born": self.world.tick if getattr(self, "world", None) else 0}
        self.axioms.append(ax)
        self.epi_stats["written"] += 1
        print("📜 {} writes an axiom: {} — and will hold reality to it".format(
            self.name, self._epi_axiom_text(ax)))

    def paradigm_shift(self, tick=None):
        """The lonk's worldview collapses. It burns its axioms, revalues
        everything it cares about, and asks a new question instead."""
        if tick is None:
            tick = self.world.tick if getattr(self, "world", None) else 0
        burned = len(self.axioms)
        for ax in self.axioms:
            ax["state"] = "dead"
        self.axioms = []
        self.pending_predictions = []
        # Revaluation: a whole new ordering of what matters
        self.will = {a: min(5.0, max(0.2, w * random.uniform(0.3, 3.0)))
                     for a, w in self.will.items()}
        self.skepticism = 0.4
        st = self.epi_stats
        st["shifts"] += 1
        st["recent_falsified"] = 0
        st["last_shift"] = tick
        # Its new question is assembled from its own vocabulary and emotions
        pool = list(getattr(self, "vocabulary", {}).keys()) + list(getattr(self, "emotion", {}).keys())
        if not pool:
            pool = ["the meadow", "the silence", "the void", "bonking"]
        q = random.choice([
            "what if {} causes {}?",
            "why does {} follow {}?",
            "is {} secretly {}?",
            "what is {} afraid of?",
            "who benefits from {}?",
            "must {} always end in {}?",
        ])
        w1 = random.choice(pool)
        w2 = random.choice([x for x in pool if x != w1]) if len(pool) > 1 else random.choice(pool)
        self.paradigm = q.format(w1, w2)
        self.paradigm_focus = random.choice(
            ["emotion", "health", "crowd", "faction", "reward", "attacked"])
        print("🌀 {} undergoes a PARADIGM SHIFT! It burns {} axioms, revalues its "
              "entire will, and now asks: '{}'".format(self.name, burned, self.paradigm))

    # ============================================================
    # SERIALIZATION (FIXED: Includes all new fields)
    # ============================================================

    def to_dict(self):
        """Serialize Lonk to dictionary for saving"""
        return {
            "name": self.name,
            "semantic_id": self.semantic_id,
            "society_state": {field: getattr(self, field) for field in (
                'max_health', 'romance_partner', 'obsession', 'affinity_vector', 'parents', 'jealousy', 'city_blessings',
                'structural_anxiety_reduction', 'trance_until', 'last_shrine_tick', 'last_romance_gift',
                'last_jealousy_tick', 'vocabulary_origins', 'last_spoken', 'cultural_concepts') if hasattr(self, field)},
            "semantic_summary": getattr(self, "semantic_summary", None),
            "alive": self.alive,
            "age": self.age,
            "generation": self.generation,
            "health": self.health,
            "lifespan": self.lifespan,
            "lifecycle_version": self.lifecycle_version,
            "last_aged_tick": self.last_aged_tick,
            "death_cause": self.death_cause,
            "trauma": self.trauma,
            "learning_signal": self.learning_signal,
            "action_valence": self.action_valence,
            "faction": self.faction,
            "territory": self.territory,
            "location_reason": self.location_reason,
            "emotion": self.emotion,
            "personality": self.personality,
            "habits": self.habits,
            "memory": {
                "player_words": list(self.memory["player_words"]),
                "lonk_words": list(self.memory["lonk_words"]),
                "events": self.memory["events"],
                "player_interactions": self.memory["player_interactions"]
            },
            "long_memory": self.long_memory,
            "gossip": [list(g) for g in self.gossip],  # Convert tuples to lists
            "items": [item["name"] for item in self.items],
            "item_details": [dict(item) for item in self.items],
            "last_combat_tick": self.last_combat_tick,
            "inventory": self.inventory,
            "relationships": self.relationships,
            "grudges": self.grudges,
            "crush": self.crush,
            "catchphrase": self.catchphrase,
            "brain": self.brain.to_dict(),
            "state": self.state,
            "rival_name": self.rival.name if self.rival else None,
            "pending_retaliation_name": self.pending_retaliation.name if self.pending_retaliation else None,
            "religion_name": self.religion["name"] if self.religion else None,
            "religion_details": copy.deepcopy(self.religion),
            "faith": self.faith,
            "heretic": self.heretic,
            "coins": self.coins,
            "inventory_value": self.inventory_value,
            "blessed": self.blessed,
            "wp_role": self.wp_role,
            # Autonomous epistemology (v11)
            "axioms": self.axioms,
            "will": self.will,
            "skepticism": self.skepticism,
            "paradigm": self.paradigm,
            "paradigm_focus": self.paradigm_focus,
            "epi_stats": self.epi_stats,
            # Composable action system
            "known_verbs": self.known_verbs,
            "action_weights": self.action_weights,
            "named_combos": list(self.named_combos),
            # FIX: action_history can hold live Lonk objects in "object" -
            # save a compact serializable summary instead of raw references
            "action_history": [
                {
                    "tick": h.get("tick", 0),
                    "verb": (h.get("action") or {}).get("verb", ""),
                    "target_type": (h.get("action") or {}).get("target_type", ""),
                    "modifier": (h.get("action") or {}).get("modifier", ""),
                    "reward": float(h.get("reward", 0.0)),
                }
                for h in self.action_history[-100:]
            ],
            # Phase 2: Conversation history persistence
            "conversation_history": [c.to_dict() for c in self.conversation_history],
            "dialogue_state": getattr(self, "dialogue_state", {}),
            "wordplay_state": getattr(self, "wordplay_state", {}),
            # Phase 3: Inner monologue persistence
            "inner_monologue": self.inner_monologue.to_dict(),
        }

    @classmethod
    def from_dict(cls, data, world=None):
        """Deserialize Lonk from dictionary"""
        # FIX: Use _loading=True to skip initialization prints
        lonk = cls(name=data["name"], world=world, _loading=True)

        # Basic attributes
        lonk.semantic_id = data.get("semantic_id", lonk.semantic_id)
        lonk.semantic_summary = data.get("semantic_summary")
        for field, value in data.get('society_state', {}).items():
            if field in ('max_health', 'romance_partner', 'obsession', 'affinity_vector', 'parents', 'jealousy', 'city_blessings',
                         'structural_anxiety_reduction', 'trance_until', 'last_shrine_tick', 'last_romance_gift',
                         'last_jealousy_tick', 'vocabulary_origins', 'last_spoken', 'cultural_concepts'):
                setattr(lonk, field, value)
        lonk.alive = data.get("alive", True)
        lonk.age = data.get("age", 0)
        lonk.generation = data.get("generation", 1)
        lonk.health = data.get("health", MAX_HEALTH)
        lonk.lifespan = data.get('lifespan', lonk.lifespan)
        if data.get('lifecycle_version', 1) < 2 and lonk.alive:
            lonk.lifespan = max(lonk.lifespan, lonk._lifespan_bounds()[0])
        lonk.lifecycle_version = 2
        lonk.last_aged_tick = data.get('last_aged_tick')
        lonk.death_cause = data.get('death_cause')
        lonk.trauma = data.get("trauma", 0)
        lonk.learning_signal = data.get("learning_signal", 0.0)
        lonk.action_valence = data.get("action_valence", 0.0)
        lonk.faction = data.get("faction", None)
        lonk.territory = data.get("territory", None)
        lonk.location_reason = data.get("location_reason")
        lonk.emotion = data.get("emotion", {})
        lonk.personality = data.get("personality", {})
        lonk.habits = data.get("habits", {})
        lonk.state = data.get("state", [0.5, 0.5, 0.2, 0.3, 0.1])

        # Autonomous epistemology (v11)
        lonk.axioms = data.get("axioms", [])
        lonk.pending_predictions = []
        lonk.will = data.get("will", {a: 1.0 for a in lonk.ACTIONS})
        lonk.skepticism = float(data.get("skepticism", 0.5))
        lonk.paradigm = data.get("paradigm", "how do I keep living?")
        lonk.paradigm_focus = data.get("paradigm_focus", "health")
        lonk.epi_stats = data.get("epi_stats", {
            "written": 0, "canonized": 0, "falsified": 0,
            "shifts": 0, "recent_falsified": 0, "last_shift": -999})
        for ax in lonk.axioms:
            for k in ("hits", "misses"):
                ax[k] = int(ax.get(k, 0))
            ax["state"] = ax.get("state", "testing")

        # Memory
        memory_data = data.get("memory", {})
        lonk.memory["player_words"] = set(memory_data.get("player_words", []))
        lonk.memory["lonk_words"] = set(memory_data.get("lonk_words", []))
        lonk.memory["events"] = memory_data.get("events", [])
        lonk.memory["player_interactions"] = memory_data.get("player_interactions", [])

        # Gossip
        lonk.gossip = []
        for g in data.get("gossip", []):
            # Handle both old format (3-tuple) and new format (4-tuple with weight)
            if len(g) == 3:
                lonk.gossip.append(tuple(g) + (1,))
            else:
                lonk.gossip.append(tuple(g))

        # Items
        if 'item_details' in data:
            lonk.items = [dict(item) for item in data['item_details']]
        else:
            lonk.items = []
            for name in data.get("items", []):
                item = next((dict(item) for item in ITEMS if item["name"] == name),
                            {'name': name, 'description': 'a saved gift', 'shiny': False})
                lonk.items.append(item)
        lonk.inventory = [item['name'] for item in lonk.items]
        lonk.last_combat_tick = data.get('last_combat_tick', -100)

        # Social
        lonk.relationships = data.get("relationships", {})
        lonk.grudges = data.get("grudges", {})
        lonk.crush = data.get("crush", None)
        lonk.catchphrase = data.get("catchphrase", None)

        # Brain
        if "brain" in data:
            lonk.brain = LonkBrain.from_dict(data["brain"], lonk.name)
        else:
            lonk.brain = LonkBrain(lonk.name)

        # Rival
        rival_name = data.get("rival_name", None)
        if rival_name:
            lonk.rival = next((other for other in (world.lonks if world else [])
                              if other.name == rival_name), None)

        # Pending retaliation
        pending_name = data.get("pending_retaliation_name", None)
        if pending_name:
            lonk.pending_retaliation = next((other for other in (world.lonks if world else [])
                                           if other.name == pending_name), None)

        # Religion
        lonk.faith = data.get("faith", random.randint(30, 100))
        lonk.heretic = data.get("heretic", False)
        religion_name = data.get("religion_name", None)
        if religion_name:
            for faction, religion in RELIGIONS.items():
                if religion["name"] == religion_name:
                    lonk.religion = religion
                    break

        if data.get('religion_details') is not None:
            lonk.religion = copy.deepcopy(data['religion_details'])

        # Finance
        lonk.coins = data.get("coins", 0)
        lonk.inventory_value = data.get("inventory_value", 0)
        lonk.blessed = data.get("blessed", False)
        lonk.wp_role = data.get("wp_role", None)

        # Composable action system
        lonk.known_verbs = data.get("known_verbs", dict(cls.VERBS))
        lonk.known_verbs.setdefault('help', dict(cls.VERBS['help']))
        lonk.action_weights = data.get("action_weights", {})
        lonk.named_combos = set(data.get("named_combos", []))
        lonk.action_history = data.get("action_history", [])

        # Phase 2: Restore conversation history (but not active conversations)
        # Active conversations will be rebuilt during simulation
        lonk.conversation_history = [
            Conversation.from_dict(c) for c in data.get("conversation_history", [])
        ]
        lonk.dialogue_state = data.get("dialogue_state", {})
        lonk.wordplay_state = data.get("wordplay_state", {})
        lonk.active_conversations = {}  # Will be rebuilt during simulation
        lonk.dialogue_memory = deque(maxlen=20)  # Will be rebuilt during simulation
        
        # Phase 3: Restore inner monologue
        if "inner_monologue" in data:
            lonk.inner_monologue = LonkInnerMonologue.from_dict(data["inner_monologue"])
        else:
            lonk.inner_monologue = LonkInnerMonologue(lonk.name)
        lonk.inner_thoughts = []  # Fresh list will be filled during simulation


        # Ensure all keys exist
        lonk.ensure_emotion_keys()
        lonk.ensure_personality_keys()
        lonk.world = world

        # FIX: Call initialization methods after loading
        if lonk.faction is None:
            lonk.join_random_faction()
        if lonk.territory is None:
            lonk.wander()
        lonk.init_social()

        return lonk

# ============================================================
# WEIGHT-SPACE PROGRAMMER (CSAIL homage)
# ------------------------------------------------------------
# An external "programmer" reads the chosen Lonk's TinyNN
# weights and rewrites them DIRECTLY - no gradient descent,
# no training data. Two programmers are provided:
#   * AnalyticalProgrammer - offline, no API needed. Inspects
#     hidden activations and habits, then patches weights
#     by rule (revives dead ReLU units, rebalances habits).
#   * LLMProgrammer - sends a "weight card" to any OpenAI-
#     compatible chat endpoint and applies the JSON patches
#     it returns. Configure with env vars:
#       WP_API_KEY   (or OPENAI_API_KEY)
#       WP_MODEL     (default: gpt-4o-mini)
#       WP_BASE_URL  (default: https://api.openai.com/v1)
# The chosen (blessed) Lonk still learns by backprop between
# edits; a CONTROL TWIN lives the same life but is never edited,
# and each edit's effect is A/B-measured (reward window before
# vs. after the edit). Use the `report` command to see it all.
# ============================================================

class WeightSpaceProgrammer:
    """Base class: builds weight cards and safely applies patches."""

    def build_weight_card(self, lonk):
        """Human/LLM-readable summary of a Lonk's TinyNN."""
        nn = lonk.brain.nn
        lines = []
        lines.append("AGENT: " + lonk.name + " (blessed - weights edited directly; backprop continues between edits)")
        lines.append("ACTIONS (output dims 0-5): " + str(Lonk.ACTIONS))
        lines.append(
            "STATE INPUT (32 dims): [0-4] Psi/theta/arousal/valence/prediction-error; "
            "[5-9] personality aggression/curiosity/anxiety/loyalty/playfulness; "
            "[10] health; [11] age; [12] faction idx; [13] territory idx; "
            "[14] item count; [15] shiny count; [16] friends; [17] enemies; "
            "[18] social strength; [19] gossip load; [20] has religion; [21] faith; "
            "[22] coins; [23] inventory value; [24-28] vitals trace/entropy/coherence/drift/dream; "
            "[29-30] tiny noise"
        )
        lines.append("ARCHITECTURE: W1 (32x16) -> ReLU -> W2 (16x6) -> softmax over actions")
        lines.append("REWARD: health gains + growth in joy/courage/power/wisdom - anxiety penalty")
        lines.append("")
        lines.append("W2 (16x6) full matrix, rows = hidden units, cols = actions:")
        for r in range(nn.W2.shape[0]):
            row = ", ".join("{:+.4f}".format(v) for v in nn.W2[r])
            lines.append("  h{:02d}: [{}]".format(r, row))
        lines.append("b2 (6): [{}]".format(", ".join("{:+.4f}".format(v) for v in nn.b2)))
        lines.append("b1 (16): [{}]".format(", ".join("{:+.4f}".format(v) for v in nn.b1)))
        lines.append("W1 (32x16) row summaries (per input dim):")
        for i in range(nn.W1.shape[0]):
            lines.append("  in{:02d}: mean={:+.4f} std={:.4f}".format(i, nn.W1[i].mean(), nn.W1[i].std()))
        hist = list(getattr(lonk, "reward_history", []))
        if hist:
            recent = hist[-50:]
            lines.append("PERFORMANCE: avg reward last {} ticks = {:+.4f}".format(len(recent), sum(recent) / len(recent)))
        lines.append("HABITS (action counts): " + str(dict(lonk.habits)))
        lines.append("EMOTION: " + str(lonk.emotion))
        return "\n".join(lines)

    def apply_patch(self, lonk, patch):
        """Apply a JSON patch to a Lonk's weights. Returns (applied, rejected)."""
        nn = lonk.brain.nn
        applied = rejected = 0
        plist = patch.get("patches") or []
        if not isinstance(plist, list):
            plist = []

        def _idx(v, limit):
            if isinstance(v, bool):
                return None
            if isinstance(v, (int, float)) and float(v).is_integer():
                v = int(v)
                return v if 0 <= v < limit else None
            return None

        for p in plist[:WP_MAX_PATCH]:
            if not isinstance(p, dict):
                rejected += 1
                continue
            name = p.get("matrix")
            if name not in ("W1", "W2", "b1", "b2"):
                rejected += 1
                continue
            val = p.get("value")
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                rejected += 1
                continue
            val = float(np.clip(float(val), -2.0, 2.0))
            m = {"W1": nn.W1, "W2": nn.W2, "b1": nn.b1, "b2": nn.b2}[name]
            i = _idx(p.get("i"), m.shape[0])
            if i is None:
                rejected += 1
                continue
            if m.ndim == 1:
                m[i] = val
                applied += 1
            else:
                j = _idx(p.get("j"), m.shape[1])
                if j is None:
                    rejected += 1
                    continue
                m[i, j] = val
                applied += 1
        return applied, rejected


class AnalyticalProgrammer(WeightSpaceProgrammer):
    """Offline weight editor: revives dead hidden units, rebalances habits."""

    name = "analytical"

    def program(self, lonk):
        nn = lonk.brain.nn
        patches = []
        notes = []

        # 1) Revive dead hidden units (ReLU units that never fire on recent states)
        states = [s for s, a, r, s2 in list(lonk.brain.buffer.buffer)[-50:]]
        if states:
            X = np.array(states)
            H = np.maximum(0, np.dot(X, nn.W1) + nn.b1)
            dead = [j for j in range(H.shape[1]) if H[:, j].sum() == 0]
            if dead:
                j = dead[0]  # revive one unit per edit
                for i in range(nn.W1.shape[0]):
                    patches.append({"matrix": "W1", "i": i, "j": j,
                                    "value": round(float(np.random.randn() * 0.1), 4)})
                patches.append({"matrix": "b1", "i": j, "value": 0.01})
                notes.append("revived dead hidden unit h{}".format(j))

        # 2) Rebalance habit collapse: damp the over-used action, boost the neglected one
        total = sum(lonk.habits.values())
        if total >= 10:
            shares = {a: lonk.habits.get(a, 0) / total for a in Lonk.ACTIONS}
            a_top = max(shares, key=shares.get)
            a_low = min(shares, key=shares.get)
            i_top, i_low = Lonk.ACTIONS.index(a_top), Lonk.ACTIONS.index(a_low)
            for h in range(nn.W2.shape[0]):
                patches.append({"matrix": "W2", "i": h, "j": i_top,
                                "value": round(float(nn.W2[h, i_top] * 0.7), 4)})
                patches.append({"matrix": "W2", "i": h, "j": i_low,
                                "value": round(float(nn.W2[h, i_low] * 1.3), 4)})
            patches.append({"matrix": "b2", "i": i_top,
                            "value": round(float(nn.b2[i_top] - 0.05), 4)})
            notes.append("damped '{}', amplified '{}'".format(a_top, a_low))

        if not patches:
            # 3) Nothing broken? Try something: a small exploration mutation,
            # so the lineage's treatment is never a no-op. The A/B report
            # will judge whether these nudges help or hurt.
            for _ in range(10):
                if random.random() < 0.5:
                    patches.append({"matrix": "W1",
                                    "i": random.randrange(nn.W1.shape[0]),
                                    "j": random.randrange(nn.W1.shape[1]),
                                    "value": round(float(np.random.randn() * 0.1), 4)})
                else:
                    patches.append({"matrix": "W2",
                                    "i": random.randrange(nn.W2.shape[0]),
                                    "j": random.randrange(nn.W2.shape[1]),
                                    "value": round(float(np.random.randn() * 0.1), 4)})
            notes.append("injected exploration noise into 10 weights")

        applied, rejected = self.apply_patch(lonk, {"patches": patches})
        return "{} ({} weights patched, {} rejected)".format("; ".join(notes), applied, rejected)


class LLMProgrammer(WeightSpaceProgrammer):
    """Sends the weight card to an OpenAI-compatible endpoint, applies returned patches."""

    name = "llm"

    def __init__(self):
        self.api_key = os.environ.get("WP_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = (os.environ.get("WP_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("WP_MODEL") or "gpt-4o-mini"

    @property
    def available(self):
        # A keyed cloud endpoint, or a keyless local one (e.g. Ollama via
        # WP_BASE_URL=http://localhost:11434/v1)
        return bool(self.api_key or os.environ.get("WP_BASE_URL"))

    def _chat(self, system, user, timeout=None):
        import urllib.request
        import urllib.error
        if timeout is None:
            # Local models (Ollama) can take minutes per reply, especially
            # thinking models on CPU. Override with the WP_TIMEOUT env var.
            try:
                timeout = int(os.environ.get("WP_TIMEOUT", "300"))
            except ValueError:
                timeout = 300
        payload = json.dumps({
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + (self.api_key or ""),
            },
            method="POST",
        )
        # v12 heartbeat: run the HTTP call in a worker thread and print
        # progress while the model thinks, so "slow" is never mistaken
        # for "stuck". We enforce the total timeout ourselves.
        import threading
        result = {}

        def _worker():
            try:
                with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                result["content"] = data["choices"][0]["message"]["content"]
            except Exception as e:
                result["error"] = e

        worker_t = threading.Thread(target=_worker, daemon=True)
        worker_t.start()
        waited = 0
        while worker_t.is_alive():
            worker_t.join(15)
            if worker_t.is_alive():
                waited += 15
                print("  🧠 model still thinking... {}s elapsed (timeout {}s)".format(
                    waited, timeout), flush=True)
                if waited >= timeout:
                    raise TimeoutError(
                        "gave up after {}s - set WP_TIMEOUT higher or use a smaller model".format(timeout))
        if "error" in result:
            e = result["error"]
            if "timed out" in str(e).lower() or isinstance(getattr(e, "reason", None), TimeoutError):
                raise TimeoutError(
                    "timed out after {}s (try a smaller model, or set WP_TIMEOUT higher)".format(timeout))
            raise e
        return result["content"]

    def program(self, lonk):
        if not self.available:
            return "LLM mode unavailable: set WP_API_KEY (or OPENAI_API_KEY)"
        system = (
            "You are a Weight-Space Programmer. You read the raw numerical weights of a tiny "
            "reinforcement-learning agent and improve them by writing weight patches directly - "
            "no gradient descent. Reason about what each layer computes, then make small, "
            "targeted edits. Respond with ONLY a JSON object, no other text."
        )
        user = self.build_weight_card(lonk) + (
            "\n\nTASK: improve this agent's brain with targeted weight patches.\n"
            "REPLY FORMAT (JSON only):\n"
            '{"analysis": "one or two sentences of reasoning", "patches": '
            '[{"matrix": "W1|W2|b1|b2", "i": <int>, "j": <int>, "value": <float>}, ...]}\n'
            "For b1/b2 patches omit \"j\". Use at most " + str(WP_MAX_PATCH) + " patches."
        )
        text = self._chat(system, user)
        # Qwen3 and other thinking models may prepend a <think> block -
        # let them reason, then keep only the final answer
        if "</think>" in text:
            text = text.split("</think>", 1)[1].strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return "LLM reply contained no JSON - no weights changed"
        patch = json.loads(text[start:end + 1])
        applied, rejected = self.apply_patch(lonk, patch)
        analysis = str(patch.get("analysis", ""))[:200]
        return "{} ({} weights patched, {} rejected)".format(analysis, applied, rejected)


# ============================================================
# LONK WORLD CLASS (FIXED: Tick management, birth queuing)
# ============================================================

class LonkWorld:
    def __init__(self, num_lonks=STARTING_POPULATION, config_file=None):
        self.lonks = []
        self.tick = 0
        self.pending_births = []  # FIX: Queue for births
        
        # Load config from LonkWorld.xc if provided
        self.config = self._load_config(config_file)
        self.semantic_trace = SemanticTrace(self.config.get("semantic_trace_path", "lonk_semantic_events.jsonl"))
        self.civilization = Civilization(self, TERRITORIES, FACTIONS, ITEM_VALUES,
                                         lambda name: Lonk(name=name, world=self, _loading=True))
        
        # Extract world parameters from config
        world_cfg = self.config.get("world", {})
        self.starting_population = world_cfg.get("starting_population", num_lonks or STARTING_POPULATION)
        self.max_population = world_cfg.get("max_population", 50)
        self.social_chance = world_cfg.get("social_chance", 0.5)
        self.rumor_mutation_chance = world_cfg.get("rumor_mutation_chance", 0.2)
        self.speech_chance = world_cfg.get("speech_chance", 0.25)
        self.dream_chance = world_cfg.get("dream_chance", 0.12)
        self.relationship_decay = world_cfg.get("relationship_decay", 0.997)
        self.rebirth_chance = world_cfg.get("rebirth_chance", 0.8)
        self.arrival_chance = world_cfg.get("arrival_chance", 0.05)
        self.item_chance = world_cfg.get("item_chance", 0.4)
        self.inheritance_mutation = world_cfg.get("inheritance_mutation", 8)
        self.crush_chance = world_cfg.get("crush_chance", 0.1)
        self.catchphrase_chance = world_cfg.get("catchphrase_chance", 0.05)
        self.recall_chance = world_cfg.get("recall_chance", 0.3)
        
        # Phase 1: Initialize command parser (v14)
        self.command_parser = CommandParser()

        # Create initial Lonks
        for _ in range(num_lonks):
            lonk = Lonk(world=self)
            self._unique_name(lonk)
            self.lonks.append(lonk)

        # Weight-space programming experiment
        self.wp_log = []
        self.wp_ab_log = []    # pre/post edit A/B records
        self.wp_ab_state = {}  # lonk name -> reward-window mean at its last edit
        self.wp_prophet_brain = None  # last chosen brain dict (soul inheritance)
        self.wp_control_brain = None  # last control brain dict (soul inheritance)
        self.wp_prophet_paradigm = None  # the chosen one's Question (v11)
        self.wp_control_paradigm = None  # the control's Question (v11)
        self.programmer = None
        self.wp_mode = None
        if TOGGLES.get("weight_programming", False):
            self.setup_weight_programming()
        
        # TTS and auto mode support
        self.tts_enabled = False
        self.tts_engine = None
        self.auto_mode = False
        self.auto_speed = 1.0  # Seconds between ticks in auto mode
        
        # TTS queue and thread for non-blocking speech
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        self.tts_running = False
        
        self.tts_ready = threading.Event()
        self.tts_error = None
        if TTS_AVAILABLE:
            print("TTS available! Use /tts on to enable voice")
        else:
            print("TTS unavailable: install pyttsx3 with python -m pip install pyttsx3")

    def _load_config(self, config_file):
        """Load world configuration from LonkWorld.xc or return defaults"""
        if config_file:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # XC format: "application LonkWorld { JSON } // comment xembra LonkMind ..."
                # Extract JSON from between the braces, stopping at the closing }
                if content.strip().startswith('application'):
                    # Find the first '{' and extract balanced braces
                    start = content.find('{')
                    if start == -1:
                        raise ValueError("No opening brace found")
                    
                    # Find matching closing brace
                    brace_count = 0
                    end = -1
                    for i in range(start, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end = i
                                break
                    
                    if end == -1:
                        raise ValueError("No matching closing brace found")
                    
                    json_str = content[start:end+1]
                    config = json.loads(json_str)
                    print(f"🔧 Loaded config from {config_file}")
                    return config
                else:
                    # Try parsing as pure JSON
                    config = json.loads(content)
                    print(f"🔧 Loaded config from {config_file}")
                    return config
            except FileNotFoundError:
                print(f"⚠️  Config file {config_file} not found, using defaults")
                return {}
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️  Error parsing {config_file}: {e}, using defaults")
                return {}
        return {}

    def world_tick(self):
        """Voice all printed tick events in order, including legacy prints."""
        live = None
        if (getattr(self, 'civilization', None) is not None and getattr(self, 'live_map_enabled', True)
                and (getattr(self, '_live_view', None) is not None or getattr(sys.stdout, 'isatty', lambda: False)())):
            live = getattr(self, '_live_view', None)
            if live is None:
                live = self._live_view = TerminalWorldView(self, sys.stdout)
            if not live.enabled or not live.fits_terminal():
                live = None
        self._live_active = live
        previous_youtube_active = getattr(self, '_youtube_active', False)
        self._youtube_active = True
        try:
            if live:
                live.begin_tick()
            if live or (self.tts_enabled and self.tts_engine is not None):
                output = _TickSpeechOutput(self, sys.stdout)
                with redirect_stdout(output):
                    try:
                        self._advance_world_tick()
                    finally:
                        output.finish()
            else:
                self._advance_world_tick()
        finally:
            self._youtube_active = previous_youtube_active
            self._live_active = None
            if live:
                live.finish_tick()
        if not live and getattr(self, 'civilization', None) is not None:
            print(self.civilization.command('map', ''), flush=True)

    def _advance_world_tick(self):
        """Advance the world by one tick"""
        self.tick += 1

        # Process pending births from previous tick
        capacity = max(0, self.max_population - sum(p.alive for p in self.lonks))
        for new_lonk in self.pending_births[:capacity]:
            self._unique_name(new_lonk)
            self.lonks.append(new_lonk)
            print(f"🌱 A new Lonk emerges: {new_lonk.name} (Gen {new_lonk.generation})")
        self.pending_births = []

        # Soul inheritance: preserve prophet/control brains before removal,
        # and clean up per-name A/B baselines of the dead
        for l in self.lonks:
            if not l.alive:
                self.wp_ab_state.pop(l.name, None)
                if getattr(l, "blessed", False):
                    self.wp_prophet_brain = l.brain.to_dict()
                    self.wp_prophet_paradigm = getattr(l, "paradigm", None)
                    l.blessed = False  # the role passes on with the soul
                elif getattr(l, "wp_role", None) == "control":
                    self.wp_control_brain = l.brain.to_dict()
                    self.wp_control_paradigm = getattr(l, "paradigm", None)
                    l.wp_role = None

        # Remove dead Lonks
        self.lonks = [l for l in self.lonks if l.alive]

        youtube = getattr(self, 'youtube_bridge', None)
        if youtube:
            self._drain_youtube()
        library = getattr(self, 'quote_library', None)
        if library:
            library.maybe_teach(self)
        self.civilization.begin_tick()
        # Tick each Lonk
        for lonk in list(self.lonks):
            if lonk.alive:
                if random.random() < self.dream_chance:
                    lonk.dream()
                action = lonk.choose_action()
                lonk.act(action)
                
                # Generate inner thoughts (1-2 per tick with configurable chance)
                if random.random() < 0.3:  # inner monologue frequency
                    thought = lonk.inner_monologue.generate_thought(lonk)
                    lonk.inner_thoughts.append(thought)
                if youtube:
                    self._drain_youtube()


        # Annex scheduling is a single bounded second pass, never recursive.
        for lonk in self.civilization.extra_turns():
            if lonk.alive:
                lonk.act(lonk.choose_action())
                if youtube:
                    self._drain_youtube()
        self.civilization.finish_tick()

        # Spawn new Lonks if population is low
        if (len(self.lonks) < self.starting_population
                and sum(p.alive for p in self.lonks) + len(self.pending_births) < self.max_population
                and random.random() < self.arrival_chance):
            new_lonk = Lonk(world=self)
            self.pending_births.append(new_lonk)

        # Weight-Space Programming: edit the chosen brain at intervals
        if getattr(self, "programmer", None):
            if self.tick % WP_INTERVAL == 0:
                self.weight_programming_step()
            if self.tick % WP_REPORT_INTERVAL == 0:
                self.wp_report()

        # AUTONOMOUS EPISTEMOLOGY: on schedule, one lonk writes a new axiom
        if EPISTEMOLOGY_ON and self.lonks and self.tick % EPI_AXIOM_INTERVAL == 0:
            random.choice(self.lonks).compose_axiom()

    @contextmanager
    def live_command_output(self):
        """Use the same event/map pipeline for player-caused world changes."""
        live = getattr(self, '_live_view', None)
        if not live or not live.enabled or not live.fits_terminal() or not getattr(self, 'live_map_enabled', True):
            yield
            return
        previous = getattr(self, '_live_active', None)
        self._live_active = live
        output = _TickSpeechOutput(self, sys.stdout)
        try:
            with redirect_stdout(output):
                try:
                    yield
                finally:
                    output.finish()
        finally:
            self._live_active = previous
            live.finish_tick()

    def quote_command(self, raw):
        if not hasattr(self, 'quote_library'):
            self.quote_library = QuoteLibrary()
        return self.quote_library.command(self, raw)

    def youtube_command(self, raw):
        if not hasattr(self, 'youtube_bridge'):
            self.youtube_bridge = YouTubeBridge()
        action = raw.strip().lower()
        if action == 'setup':
            import getpass
            import warnings
            if not sys.stdin.isatty():
                raise ValueError('Run /youtube setup in an interactive terminal so the key can stay hidden.')
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', getpass.GetPassWarning)
                    key = getpass.getpass('YouTube Data API key (hidden): ')
            except getpass.GetPassWarning:
                raise ValueError('Hidden input unavailable. Run setup in an interactive PowerShell terminal.') from None
            except KeyboardInterrupt:
                return 'YouTube setup cancelled.'
            return self.youtube_bridge.setup(key)
        if action == 'pump':
            return f'YouTube: applied {self.youtube_bridge.drain(self, force=True)} queued message.'
        return self.youtube_bridge.command(raw)

    def _stop_youtube(self):
        youtube = getattr(self, 'youtube_bridge', None)
        if youtube:
            youtube.close()

    def _drain_youtube(self):
        youtube = getattr(self, 'youtube_bridge', None)
        if youtube is None or getattr(self, '_draining_youtube', False):
            return 0
        self._draining_youtube = True
        try:
            return youtube.drain(self)
        finally:
            self._draining_youtube = False

    def get_lonk(self, name):
        """Get a Lonk by name"""
        for lonk in self.lonks:
            if lonk.name == name:
                return lonk
        return None

    def narrate(self, line):
        depth = getattr(self, '_narration_depth', 0)
        self._narration_depth = depth+1
        try:
            result = self._narrate_line(line)
        finally:
            self._narration_depth = depth
        if depth == 0 and getattr(self, '_youtube_active', False):
            self._drain_youtube()
        return result

    def _narrate_line(self, line):
        """Type one line while speaking it, then advance to the next event."""
        if isinstance(sys.stdout, _TickSpeechOutput):
            output = sys.stdout
            output.finish()
            with redirect_stdout(output.output):
                return self.narrate(line)
        live = getattr(self, '_live_active', None)
        if live and not getattr(self, '_narrating_live', False):
            self._narrating_live = True
            try:
                return live.narrate(line, lambda: self.narrate(line))
            finally:
                self._narrating_live = False
        if isinstance(sys.stdout, ColorOutput):
            with redirect_stdout(sys.stdout.output):
                print(event_color(line), end='', flush=True)
                try:
                    return self.narrate(line)
                finally:
                    print(RESET, end='', flush=True)
        if not (self.tts_enabled and self.tts_engine is not None):
            print(line, flush=True)
            return
        completed = threading.Event()
        progress = queue.Queue() if getattr(self, 'tts_word_events', False) else None
        self.speak(None, line, completed=completed, progress=progress)
        try:
            if progress is not None:
                self._type_with_voice(line, progress, completed)
            else:
                for character in line:
                    print(character, end="", flush=True)
                    time.sleep(0.035)
        finally:
            print(flush=True)
        while self.tts_running and not completed.wait(timeout=0.1):
            pass

    def _type_with_voice(self, line, progress, completed):
        """Anchor each word to SAPI's playback events; smooth its letters."""
        cursor = target = 0
        delay = 0.045
        previous = None
        next_letter = time.monotonic()
        while True:
            try:
                start, end, timestamp = progress.get(timeout=0.01)
                if previous is not None:
                    last_start, last_time = previous
                    span = start - last_start
                    if span > 0:
                        delay = max(0.01, min(0.15, (timestamp - last_time) / span))
                previous = (start, timestamp)
                # A new spoken word is authoritative: catch up any earlier letters.
                while cursor < start:
                    print(line[cursor], end="", flush=True)
                    cursor += 1
                target = max(target, end)
                next_letter = time.monotonic()
            except queue.Empty:
                pass
            now = time.monotonic()
            if cursor < target and now >= next_letter:
                print(line[cursor], end="", flush=True)
                cursor += 1
                next_letter = now + delay
            if completed.is_set() or not self.tts_running:
                print(line[cursor:], end="", flush=True)
                break

    @staticmethod
    def _speech_text(full_text):
        """Map SAPI UTF-16 word offsets back to the decorated display line."""
        text, indices = [], []
        for index, character in enumerate(full_text):
            replacement = ' to ' if character == '\u2192' else character
            for letter in replacement:
                if letter.isalnum() or letter.isspace() or letter in "'.,!?:;-/":
                    text.append(letter)
                    indices.extend([index] * (len(letter.encode('utf-16-le')) // 2))
        return ''.join(text), indices

    def speak(self, speaker_name, message, wait=False, completed=None, progress=None):
        """Queue speech, optionally pacing the simulation to this utterance."""
        if self.tts_enabled and self.tts_engine:
            if completed is None:
                completed = threading.Event()
            self.tts_queue.put((speaker_name, message, completed, progress))
            if wait:
                while self.tts_running and not completed.wait(timeout=0.1):
                    pass
            return True
        return False

    def _tts_worker(self):
        """Create and use the speech engine on its owning thread."""
        com = None
        events = None
        self.tts_word_events = False
        try:
            if sys.platform == "win32":
                import pythoncom
                pythoncom.CoInitialize()
                com = pythoncom
                from win32com.client import gencache, WithEvents, constants
                self.tts_engine = gencache.EnsureDispatch("SAPI.SpVoice")
                self.tts_engine.Rate = -1
                class VoiceEvents:
                    progress = None
                    indices = []
                    ended = False

                    def OnWord(sink, stream, position, character, length):
                        if sink.progress is not None and length and character < len(sink.indices):
                            end = min(character + length, len(sink.indices))
                            sink.progress.put((sink.indices[character], sink.indices[end - 1] + 1, time.monotonic()))

                    def OnEndStream(sink, stream, position):
                        sink.ended = True

                events = WithEvents(self.tts_engine, VoiceEvents)
                self.tts_engine.EventInterests = constants.SVEEndInputStream | constants.SVEWordBoundary
                self.tts_word_events = True
            else:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
            self.tts_ready.set()
            while self.tts_running:
                try:
                    speaker_name, message, completed, progress = self.tts_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if message:
                        full_text = f"{speaker_name}: {message}" if speaker_name else message
                        # Keep decorative icons in the display, not in the voice.
                        spoken_text, indices = self._speech_text(full_text)
                        if com is not None:
                            events.progress = progress
                            events.indices = indices
                            events.ended = False
                            self.tts_engine.Speak(spoken_text, constants.SVSFlagsAsync | constants.SVSFIsNotXML)
                            while self.tts_running and not events.ended:
                                com.PumpWaitingMessages()
                                if self.tts_engine.WaitUntilDone(0):
                                    com.PumpWaitingMessages()
                                    break
                                time.sleep(0.005)
                        else:
                            self.tts_engine.say(spoken_text)
                            self.tts_engine.runAndWait()
                finally:
                    self.tts_queue.task_done()
                    completed.set()
        except Exception as exc:
            self.tts_error = str(exc)
        finally:
            self.tts_enabled = False
            self.tts_running = False
            self.tts_word_events = False
            if events is not None:
                events.close()
            if self.tts_engine is not None:
                try:
                    if com is not None:
                        self.tts_engine.Speak("", 3)  # Purge any pending SAPI speech.
                    else:
                        self.tts_engine.stop()
                except Exception as exc:
                    self.tts_error = str(exc)
            self.tts_engine = None
            if com is not None:
                com.CoUninitialize()
            self.tts_ready.set()

    def _start_tts_thread(self):
        """Wait for initialization so enabling cannot silently fail."""
        if self.tts_thread and self.tts_thread.is_alive():
            return self.tts_running and self.tts_engine is not None
        if not TTS_AVAILABLE:
            return False
        self.tts_error = None
        self.tts_ready.clear()
        self.tts_running = True
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()
        if not self.tts_ready.wait(timeout=10):
            self.tts_running = False
            print("TTS initialization timed out")
            return False
        return self.tts_running and self.tts_engine is not None

    def _stop_tts_thread(self):
        """Stop accepting speech and discard pending messages."""
        self.tts_enabled = False
        self.tts_running = False
        while True:
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break
        if self.tts_thread:
            self.tts_thread.join(timeout=1.0)

    def _unique_name(self, lonk):
        """Ensure no two living Lonks share a name (A/B stats are keyed by name)."""
        names = {l.name for l in self.lonks}
        while lonk.name in names:
            lonk.name = generate_name()
        return lonk.name

    # ============================================================
    # WEIGHT-SPACE PROGRAMMING (CSAIL homage)
    # ============================================================

    def setup_weight_programming(self):
        """Pick a programmer and designate the chosen Lonk plus an un-edited control twin."""
        llm = LLMProgrammer()
        if llm.available:
            self.programmer = llm
            self.wp_mode = "llm"
            print("🧬 Weight-Space Programming: LLM mode ({})".format(llm.model))
        else:
            self.programmer = AnalyticalProgrammer()
            self.wp_mode = "analytical"
            print("🧬 Weight-Space Programming: analytical mode (set WP_API_KEY to enable LLM mode)")
        chosen = next((l for l in self.lonks if getattr(l, "blessed", False)), None)
        if chosen is None and self.lonks:
            chosen = random.choice(self.lonks)
            chosen.blessed = True
        if chosen:
            chosen.wp_role = "chosen"
            print("🧬 {} is CHOSEN — the programmer may rewrite its weights directly".format(chosen.name))
        self.ensure_control_twin()

    def ensure_control_twin(self):
        """Keep exactly one un-edited control twin alive for comparison."""
        control = next((l for l in self.lonks if getattr(l, "wp_role", None) == "control" and l.alive), None)
        if control is not None:
            return
        candidates = [l for l in self.lonks if l.alive and not getattr(l, "blessed", False)]
        if not candidates:
            return
        # Prefer the youngest non-chosen lonk to keep life stages aligned
        control = min(candidates, key=lambda l: l.age)
        control.wp_role = "control"
        print("🧬 {} is the CONTROL TWIN — same life, same world, weights never edited".format(control.name))
        # Soul inheritance for the control too: same rule, but its brain is
        # never directly edited — keeps the lineage comparison fair
        if self.wp_control_brain is not None:
            control.brain = LonkBrain.from_dict(self.wp_control_brain, control.name)
            control.brain.reward_system = RewardSystem()
            print("🧬 {} inherits the control lineage's brain (unedited, for fairness).".format(control.name))
            if getattr(self, "wp_control_paradigm", None):
                control.paradigm = self.wp_control_paradigm
                print("🧬 {} inherits the control Question: '{}'".format(control.name, control.paradigm))

    def weight_programming_step(self):
        """Run the programmer on the chosen Lonk right now."""
        if not getattr(self, "programmer", None):
            print("🧬 weight-space programming is disabled (TOGGLES['weight_programming'])")
            return
        chosen = next((l for l in self.lonks if getattr(l, "blessed", False) and l.alive), None)
        if chosen is None:
            candidates = [l for l in self.lonks
                          if l.alive and getattr(l, "wp_role", None) != "control"]
            if not candidates:
                return
            # Prefer the youngest candidate so the prophet's edited life
            # overlaps the control twin's life stage
            chosen = min(candidates, key=lambda l: l.age)
            chosen.blessed = True
            chosen.wp_role = "chosen"
            print("🧬 The chosen one has fallen. {} is the new prophet.".format(chosen.name))
            # Soul inheritance: the prophet's EDITED weights carry forward,
            # so weight-space programming compounds across generations
            if self.wp_prophet_brain is not None:
                chosen.brain = LonkBrain.from_dict(self.wp_prophet_brain, chosen.name)
                chosen.brain.reward_system = RewardSystem()
                print("🧬 {} inherits the prophet's soul — edited weights carry forward.".format(chosen.name))
                # The Question outlives the body: the successor inherits the
                # dead prophet's paradigm, but must write its OWN axioms
                if getattr(self, "wp_prophet_paradigm", None):
                    chosen.paradigm = self.wp_prophet_paradigm
                    print("🧬 {} inherits the Question: '{}'".format(chosen.name, chosen.paradigm))
        self.ensure_control_twin()
        # Pre/post edit A/B: the window just closed (last WP_INTERVAL rewards)
        # is the AFTER-window of the previous edit; compare it to that edit's
        # BEFORE-window to measure the effect of that edit on this Lonk.
        hist = list(getattr(chosen, "reward_history", []))
        if len(hist) >= 5:
            window = hist[-WP_INTERVAL:]
            cur = sum(window) / len(window)
            prev = self.wp_ab_state.get(chosen.name)
            if prev is not None:
                self.wp_ab_log.append({
                    "tick": self.tick, "lonk": chosen.name,
                    "pre": round(prev, 4), "post": round(cur, 4),
                    "delta": round(cur - prev, 4),
                })
            self.wp_ab_state[chosen.name] = cur
        try:
            before_edit = self.civilization.snapshot(chosen)
            result = self.programmer.program(chosen)
            self.civilization.diffuse_edit(chosen, before_edit)
            print("🧬 [{}] {} edits {}: {}".format(self.tick, self.programmer.name, chosen.name, result))
            self.wp_log.append({"tick": self.tick, "lonk": chosen.name, "result": str(result)})
        except Exception as e:
            print("🧬 programming failed: {}".format(e))

    def wp_report(self):
        """Chosen vs. control twin vs. population average, plus pre/post edit A/B."""
        if not self.lonks:
            print("🧬 no lonks to report on")
            return
        chosen = next((l for l in self.lonks if getattr(l, "blessed", False) and l.alive), None)
        control = next((l for l in self.lonks if getattr(l, "wp_role", None) == "control" and l.alive), None)
        others = [l for l in self.lonks if l is not chosen and l is not control and l.alive]

        def metrics(l):
            h = list(getattr(l, "reward_history", []))
            return {
                "avg_reward": sum(h) / len(h) if h else 0.0,
                "health": l.health,
                "age": l.age,
                "joy": l.emotion.get("joy", 50),
                "items": len(l.items),
                "coins": l.coins,
            }

        print("\n" + "=" * 58)
        print("🧬 WEIGHT-SPACE PROGRAMMING REPORT (tick {})".format(self.tick))
        print("=" * 58)
        if chosen is None:
            print("No chosen Lonk alive.")
            print("=" * 58)
            return
        cm = metrics(chosen)
        print("CHOSEN: {} (Gen {}) | weights edited every {} ticks".format(
            chosen.name, chosen.generation, WP_INTERVAL))
        columns = [("chosen", cm)]
        if control is not None:
            ctm = metrics(control)
            print("CONTROL: {} | same life, weights NEVER edited".format(control.name))
            # Age-matched early-life comparison: the overlap of their youngest
            # ticks (reward_history[k] is tick k of that lonk's own life)
            ch_hist = list(getattr(chosen, "reward_history", []))
            ct_hist = list(getattr(control, "reward_history", []))
            upto = min(len(ch_hist), len(ct_hist), WP_INTERVAL)
            if upto >= 5:
                cm["early_reward"] = sum(ch_hist[:upto]) / upto
                ctm["early_reward"] = sum(ct_hist[:upto]) / upto
                print("early_reward: avg over each one's FIRST {} ticks of life (age-matched)".format(upto))
            columns.append(("control", ctm))
        if others:
            oms = [metrics(l) for l in others]
            keys = [k for k in cm if k != "early_reward"]
            columns.append(("others avg", {k: sum(m[k] for m in oms) / len(oms) for k in keys}))
        print("{:<12}".format("metric") + "".join("{:>14}".format(c) for c, _ in columns))
        for k in cm:
            row = "{:<12}".format(k)
            for _, m in columns:
                row += "{:>14.4f}".format(m[k]) if k in m else "{:>14}".format("-")
            print(row)
        # Pre/post edit A/B summary for the current chosen Lonk
        deltas = []
        rec = None
        for r in self.wp_ab_log:
            if r["lonk"] == chosen.name:
                deltas.append(r["delta"])
                rec = r
        if deltas:
            print("-" * 58)
            print("A/B for {}: {} edits measured | mean reward change {:+.4f} per edit | "
                  "latest {:+.4f} ({:+.4f} before → {:+.4f} after)".format(
                      chosen.name, len(deltas), sum(deltas) / len(deltas),
                      rec["delta"], rec["pre"], rec["post"]))
        if EPISTEMOLOGY_ON and getattr(chosen, "paradigm", None):
            print("-" * 58)
            print("The chosen one's question: '{}' | skepticism {}/0.9 | {} paradigm shifts".format(
                chosen.paradigm, round(chosen.skepticism, 2), chosen.epi_stats["shifts"]))
        print("=" * 58)

    def show_philosophy(self, name=None):
        """Inspect the lonks' self-made axioms, values, and paradigms (v11)."""
        if not EPISTEMOLOGY_ON:
            print("Autonomous epistemology is disabled (EPISTEMOLOGY_ON = False)")
            return
        print("\n" + "=" * 58)
        print("🌀 AUTONOMOUS EPISTEMOLOGY (tick {})".format(self.tick))
        print("=" * 58)
        alive = [l for l in self.lonks if l.alive]
        if name:
            lonk = self.get_lonk(name)
            if lonk is None or not lonk.alive:
                print("No living lonk named '{}'".format(name))
                return
            print("\n{}'s worldview:".format(lonk.name))
            print("  Question:    '{}'".format(lonk.paradigm))
            print("  Skepticism:  {}/0.9 — its own standard of proof".format(round(lonk.skepticism, 2)))
            will_sorted = sorted(lonk.will.items(), key=lambda kv: -kv[1])
            print("  Will:        " + ", ".join("{} {:.2f}".format(a, w) for a, w in will_sorted))
            st = lonk.epi_stats
            print("  History:     {} written, {} canonized, {} falsified, {} paradigm shifts".format(
                st["written"], st["canonized"], st["falsified"], st["shifts"]))
            if lonk.axioms:
                print("  Live axioms:")
                for ax in lonk.axioms:
                    print("    [{}] {} — {} right / {} wrong".format(
                        ax["state"], lonk._epi_axiom_text(ax), ax["hits"], ax["misses"]))
            else:
                print("  Live axioms: none — its slate is blank")
            return
        if not alive:
            print("No living lonks.")
            return
        print("{:<12} {:<28} {:>8} {:>8} {:>7}".format(
            "lonk", "question", "axioms", "shifts", "skeptic"))
        for l in alive:
            canon = sum(1 for a in l.axioms if a["state"] == "canon")
            testing = sum(1 for a in l.axioms if a["state"] == "testing")
            print("{:<12} {:<28} {:>8} {:>8} {:>7}".format(
                l.name, "'" + l.paradigm[:25] + "'",
                "{}/{}".format(canon, testing), l.epi_stats["shifts"],
                round(l.skepticism, 2)))
        print("=" * 58 + "\n")

    def save(self, filename="lonk_world.json"):
        """Save world state to file"""
        data = {
            "tick": self.tick,
            "starting_population": self.starting_population,
            "max_population": self.max_population,
            "lonks": [l.to_dict() for l in self.lonks],
            "pending_births": [l.to_dict() for l in self.pending_births],
            "quote_library": getattr(self, 'quote_library', QuoteLibrary()).to_dict(),
            "civilization": self.civilization.to_dict()
        }
        with open(filename, 'w') as f:
            # default=str: belt-and-braces so a stray object value can
            # never crash a save
            json.dump(data, f, indent=2, default=str)
        print(f"💾 World saved to {filename}")

    def load(self, filename="lonk_world.json"):
        """Load world state from file"""
        if not os.path.exists(filename):
            print(f"❌ File {filename} not found")
            return False

        with open(filename, 'r') as f:
            data = json.load(f)

        self.tick = data.get("tick", 0)
        self.quote_library = QuoteLibrary.from_dict(data.get('quote_library'))
        self.starting_population = data.get("starting_population", STARTING_POPULATION)
        self.max_population = data.get('max_population', self.max_population)
        self.lonks = []
        self.config.pop('generated_locations', None)
        self.civilization = Civilization(self, TERRITORIES, FACTIONS, ITEM_VALUES,
                                         lambda name: Lonk(name=name, world=self, _loading=True))
        self.civilization.restore(data.get('civilization'))
        self.pending_births = [Lonk.from_dict(saved, world=self) for saved in data.get('pending_births', [])]

        for lonk_data in data.get("lonks", []):
            lonk = Lonk.from_dict(lonk_data, world=self)
            self.lonks.append(lonk)

        # Phase 2: Reconnect conversation participants after all Lonks are loaded
        # This ensures Conversation objects can reference target Lonks by name
        for lonk in self.lonks:
            for conv in lonk.conversation_history:
                # Re-establish participant references from names stored in conversation
                conv.participants = []
                for participant_name in conv.participant_names:
                    target = next((other for other in self.lonks if other.name == participant_name), None)
                    if target:
                        conv.participants.append(target)

        print(f"📂 World loaded from {filename} (tick {self.tick})")
        live = getattr(self, '_live_view', None)
        if live:
            live.reset()
            if live.enabled and live.fits_terminal() and getattr(self, 'live_map_enabled', True):
                live.finish_tick()
        return True

    def interactive_loop(self):
        """Run interactive simulation loop"""
        print("\n" + "="*50)
        print("🌟 LONK WORLD BEGINS 🌟")
        print("="*50)
        print("New syntax: /say Alice hello   or   say alice hello")
        print("Type '/help' for all commands")
        print("Live map during ticks | /map for details | /live on/off to switch views")
        print("Local quote files: /quotes load FILE | /quotes teach NAME | /quotes on/off")
        print("YouTube chat: /youtube setup once | /youtube reconnect | /youtube status")
        if TTS_AVAILABLE:
            print("Type '/tts on' to enable voice | '/auto on' for auto mode")
        print("="*50 + "\n")

        while True:
            command_context = ExitStack()
            try:
                # Auto mode: advance without waiting for input
                if self.auto_mode:
                    if not (getattr(self, '_live_view', None) and self._live_view.enabled and getattr(self, 'live_map_enabled', True)):
                        print(f"[Auto tick {self.tick}] ", end="", flush=True)
                    self.world_tick()
                    time.sleep(self.auto_speed)
                    continue
                
                if self.tts_error and self.tts_error != getattr(self, '_reported_tts_error', None):
                    print(f"TTS failed: {self.tts_error}")
                    self._reported_tts_error = self.tts_error
                user_input = input("Press ENTER to advance, or type a command: ").strip()

                if not user_input:
                    # FIX: Call world_tick() instead of inline ticking
                    self.world_tick()
                    continue

                if user_input.lower() in ('/live on', '/live off'):
                    self.live_map_enabled = user_input.lower().endswith('on')
                    print('Live map ' + ('ON' if self.live_map_enabled else 'OFF'))
                    continue

                if user_input.split(None, 1)[0].lower() in ('/youtube', 'youtube'):
                    raw = user_input.split(None, 1)[1] if len(user_input.split(None, 1)) > 1 else ''
                    try:
                        if raw.strip().lower() == 'setup':
                            print(self.youtube_command(raw))
                        else:
                            with self.live_command_output():
                                print(self.youtube_command(raw))
                    except (ValueError, OSError) as exc:
                        print(f'YouTube: {exc}')
                    continue

                if user_input.split(None, 1)[0].lower() in ('/quotes', 'quotes'):
                    raw = user_input.split(None, 1)[1] if len(user_input.split(None, 1)) > 1 else ''
                    try:
                        with self.live_command_output():
                            result = self.quote_command(raw)
                            if result:
                                print(result)
                    except (ValueError, OSError) as exc:
                        print(f'Quote library: {exc}')
                    continue

                # Handle auto mode toggle
                if user_input.lower() == "/auto on":
                    self.auto_mode = True
                    print("🚀 Auto mode ON - press Ctrl+C to pause")
                    continue
                elif user_input.lower() == "/auto off":
                    self.auto_mode = False
                    print("⏸️  Auto mode OFF")
                    continue
                elif user_input.lower().startswith("/auto "):
                    try:
                        speed = float(user_input.split()[1])
                        self.auto_speed = speed
                        self.auto_mode = True
                        print(f"🚀 Auto mode ON at {speed}s per tick - press Ctrl+C to pause")
                        continue
                    except:
                        print("❌ Usage: /auto 0.5 (or /auto on/off)")
                        continue
                
                # Handle TTS toggle
                if user_input.lower() == "/tts on":
                    if self._start_tts_thread():
                        self.tts_enabled = True
                        print("🔊 TTS enabled - Lonks will speak!")
                    else:
                        print("⚠️  TTS not available (install pyttsx3)")
                    continue
                elif user_input.lower() == "/tts off":
                    self._stop_tts_thread()
                    self.tts_enabled = False
                    print("🔇 TTS disabled")
                    continue

                if user_input.lower() == "/help":
                    user_input = "help"

                # Phase 1: Try new command parser first (v14)
                cmd, args, err = self.command_parser.parse(user_input)
                
                if cmd:
                    if cmd in ({'say', 'gift', 'gossip', 'interact'} | (set(Civilization.COMMANDS) - {'map', 'market', 'society'})):
                        command_context.enter_context(self.live_command_output())
                    if cmd in Civilization.COMMANDS:
                        try:
                            print(self.civilization.command(cmd, args.get('raw', '')))
                        except (ValueError, IndexError) as exc:
                            print(f"Command error: {exc}")
                        continue
                    # New command system
                    if cmd == "say":
                        target_name = args.get("target", "")
                        message = args.get("message", "")
                        lonk = self.get_lonk(target_name)
                        if lonk:
                            print(f"🗣️ You speak to {target_name}: {message}")
                            lonk.hear("Player", message, is_player=True)
                            response = lonk.respond_to_player(message)
                            self.narrate(f"💬 {target_name} → YOU: {response}")
                        else:
                            print(f"❌ Lonk '{target_name}' not found")
                    
                    elif cmd == "observe":
                        target_name = args.get("target", "")
                        lonk = self.get_lonk(target_name)
                        if lonk:
                            print(f"\n👁️ OBSERVING {target_name}:")
                            print(f"  State: {lonk.get_xembra_state()}")
                            print(f"  Health: {lonk.health}/{getattr(lonk, 'max_health', MAX_HEALTH)}")
                            print(f"  Age: {lonk.age}/{lonk.lifespan} world ticks")
                            print(f"  Arousal: {lonk.state[2]:.2f} | Valence: {lonk.state[3]:.2f} | Trauma: {lonk.trauma:.1f}")
                            print(f"  Emotion: {lonk.emotion}")
                            print(f"  Personality: {lonk.personality}")
                            print(f"  Faction: {lonk.faction} | Room: {lonk.territory}")
                            if hasattr(lonk, 'items'):
                                print(f"  Items: {', '.join(item['name'] for item in lonk.items) or '(none)'} | Coins: {getattr(lonk, 'coins', 0):.2f}")
                        else:
                            print(f"❌ Lonk '{target_name}' not found")
                    
                    elif cmd == "listen":
                        target_name = args.get("target", "")
                        lonk = self.get_lonk(target_name)
                        if lonk:
                            print(f"\n👂 MEMORY OF {target_name}:")
                            if lonk.memory.get("events"):
                                for event in lonk.memory["events"][-5:]:
                                    print(f"  - {event}")
                            else:
                                print("  (no memories)")
                            summary = getattr(lonk, 'semantic_summary', None)
                            if summary:
                                print(f"  Interpretation: {summary['coverage']} | trace event {summary['trace_sequence']}")
                                for frame in summary['frames']:
                                    negative = 'not ' if frame.get('negative') else ''
                                    print(f"    {frame.get('subject', '')}: {negative}{frame.get('verb', frame['act'])} {frame.get('object') or '?'}")
                                if summary['unparsed']:
                                    print(f"    Still unparsed: {len(summary['unparsed'])} clause(s); original text retained in trace")
                        else:
                            print(f"❌ Lonk '{target_name}' not found")
                    
                    elif cmd == "interact":
                        target_name = args.get("target", "")
                        action = args.get("action", "greet")
                        lonk = self.get_lonk(target_name)
                        if lonk:
                            print(f"🤝 You attempt to {action} {target_name}")
                            import shlex
                            requested = shlex.split(action)
                            verb = requested[0] if requested else 'greet'
                            if verb in Lonk.VERBS or verb in Lonk.ACTIONS or verb in getattr(lonk, 'known_verbs', {}) or verb in ('follow', 'seek', 'devote', 'jealous', 'extort', 'proclaim'):
                                detail = ' '.join(requested[1:]) or None
                                obj = next((item for item in lonk.items if detail and item['name'].lower() == detail.lower()), detail)
                                directed = self.get_lonk(detail) if detail and verb in ('follow', 'seek', 'jealous', 'extort', 'help', 'bonk', 'attack', 'praise', 'insult') else None
                                result = lonk.execute_action({'verb': verb, 'target_type': 'other', 'object': obj,
                                                              'target_name': directed.name if directed else None})
                                print(f"  {target_name}: {'done' if result.get('success') else 'could not complete that action'}")
                            else:
                                response = f"{target_name} responds to your {action}."
                                print(response)
                        else:
                            print(f"❌ Lonk '{target_name}' not found")
                    
                    elif cmd == "gossip":
                        rumor = args.get("rumor", "")
                        if rumor:
                            print(f"🗨️ You spread a rumor: '{rumor}'")
                            # Seed the rumor to random Lonk
                            if self.lonks:
                                target = random.choice(self.lonks)
                                target.seed_rumor('Player', rumor)
                                print(f"  (told to {target.name})")
                        else:
                            print("Usage: /gossip <rumor>")
                    
                    elif cmd == "gift":
                        target_name = args.get("target", "")
                        emotion_type = args.get("emotion", "joy")
                        lonk = self.get_lonk(target_name)
                        if lonk:
                            print(f"🎁 You gift {target_name} some {emotion_type}")
                            print("  " + lonk.receive_gift(emotion_type))
                        else:
                            print(f"❌ Lonk '{target_name}' not found")
                    
                    continue
                
                elif err and user_input.startswith("/"):
                    # New slash syntax used but command unknown
                    print(f"❌ {err}")
                    continue
                
                # Fall back to legacy commands
                parts = user_input.split()
                command = parts[0].lower() if parts else ""

                if command == "quit" or command == "exit":
                    self.save()
                    print("👋 Goodbye!")
                    break

                elif command == "run":
                    if len(parts) > 1:
                        try:
                            n = int(parts[1])
                            print(f"⏩ Running {n} world ticks...")
                            for i in range(n):
                                self.world_tick()
                                if not (getattr(self, '_live_view', None) and self._live_view.enabled and getattr(self, 'live_map_enabled', True)):
                                    print(f"\n{'='*50}\n🌍 WORLD TICK {self.tick}\n{'='*50}\n")
                        except ValueError:
                            print("Usage: run <number>")
                    else:
                        print("Usage: run <number>")

                elif command == "stats":
                    print("\n" + "="*50)
                    print(f"🌍 WORLD STATS (Tick: {self.tick})")
                    print("="*50)
                    print(f"👥 Population: {len(self.lonks)} Lonks")
                    for lonk in self.lonks:
                        if lonk.alive:
                            state = lonk.get_xembra_state()
                            faction = lonk.faction or "None"
                            territory = lonk.territory or "None"
                            health = f"{lonk.health}/{getattr(lonk, 'max_health', MAX_HEALTH)}"
                            print(f"  - {lonk.name} (Gen {lonk.generation}): {state}, {faction}, {territory}, HP:{health}")
                    print("="*50)

                elif command == "save":
                    self.save()
                elif command == "load":
                    if self.load():
                        print("World loaded successfully!")
                    else:
                        print("Failed to load world")

                elif command == "prog":
                    self.weight_programming_step()

                elif command == "report":
                    self.wp_report()

                elif command == "philosophy":
                    self.show_philosophy(parts[1] if len(parts) > 1 else None)

                elif command == "wpmode":
                    if len(parts) > 1 and parts[1].lower() == "llm":
                        llm = LLMProgrammer()
                        if llm.available:
                            self.programmer = llm
                            self.wp_mode = "llm"
                            print("🧬 LLM mode enabled ({})".format(llm.model))
                        else:
                            print("Set WP_API_KEY first, then run: wpmode llm")
                    elif len(parts) > 1 and parts[1].lower() == "analytical":
                        self.programmer = AnalyticalProgrammer()
                        self.wp_mode = "analytical"
                        print("🧬 analytical mode enabled")
                    else:
                        print("Usage: wpmode <analytical|llm>")

                elif command == "help":
                    # Show new command help
                    print(self.command_parser.help())
                    print("\nLEGACY COMMANDS (still supported):")
                    print("  /auto on/off   - Start/stop auto mode (Ctrl+C pauses while running)")
                    print("  ENTER          - Advance one tick")
                    print("  run <n>        - Run n ticks")
                    print("  stats          - Show world stats")
                    print("  save           - Save world state")
                    print("  load           - Load world state")
                    print("  prog           - Run the weight-space programmer now")
                    print("  report         - Chosen vs. others performance report")
                    print("  philosophy [name] - A lonk's axioms, values, and question")
                    print("  wpmode <mode>  - analytical or llm weight programmer")
                    print("  quit/exit      - Quit and save")
                    print()

                else:
                    print(f"❌ Unknown command: {command}. Type 'help' for commands")

            except KeyboardInterrupt:
                if self.auto_mode:
                    self.auto_mode = False
                    # Pause without saving/exiting; leave the world available for commands.
                    print("\nAuto mode paused. Type commands, or /auto on to resume.")
                    continue
                print("\n👋 Interrupted! Saving...")
                self._stop_tts_thread()  # Cleanup TTS thread
                self.save()
                print("💾 Saved. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                command_context.close()
        
        # Final cleanup
        self._stop_youtube()
        self._stop_tts_thread()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    sys.stdout = enable_colors(sys.stdout)
    # Parse command-line arguments
    config_file = None
    num_lonks = STARTING_POPULATION
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--config" and len(sys.argv) > 2:
            config_file = sys.argv[2]
            print(f"🔧 Using config file: {config_file}")
        else:
            print(f"Usage: python {sys.argv[0]} [--config <config_file>]")
            print(f"       python {sys.argv[0]} --config LonkWorld.xc")
            sys.exit(1)
    
    # Set random seed for reproducibility (optional)
    # random.seed(42)
    # np.random.seed(42)

    world = LonkWorld(num_lonks=num_lonks, config_file=config_file)
    world.interactive_loop()
