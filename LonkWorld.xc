application LonkWorld {
  "host_version": 1,
  "title": "LonkWorld",
  "starting_population": 5,
  "max_population": 20,
  "world": {
    "starting_population": 5,
    "max_population": 20,
    "initial_state": [
      0.5,
      0.5,
      0.2,
      0.3,
      0.1
    ],
    "initial_stats": [
      20,
      80
    ],
    "lifespan": [
      90,
      180
    ],
    "social_chance": 0.5,
    "rumor_mutation_chance": 0.2,
    "speech_chance": 0.25,
    "dream_chance": 0.12,
    "relationship_decay": 0.997,
    "rebirth_chance": 0.8,
    "arrival_chance": 0.05,
    "item_chance": 0.4,
    "inheritance_mutation": 8,
    "crush_chance": 0.1,
    "catchphrase_chance": 0.05,
    "recall_chance": 0.3
  },
  "bindings": {
    "energy": "state.0",
    "expectation": "state.1",
    "arousal": "state.2",
    "valence": "state.3",
    "error": "state.4",
    "power": "emotion.power",
    "courage": "emotion.courage",
    "wisdom": "emotion.wisdom",
    "masochism": "emotion.masochism",
    "joy": "emotion.joy",
    "anxiety": "emotion.anxiety",
    "aggression": "personality.aggression",
    "curiosity": "personality.curiosity",
    "worry": "personality.anxiety",
    "loyalty": "personality.loyalty",
    "trauma": "trauma",
    "dopamine": "dopamine"
  },
  "inputs": {
    "sensory": "uniform",
    "arousal_noise": "centered_uniform",
    "energy_noise": "centered_uniform",
    "attack_noise": "gumbel",
    "explore_noise": "gumbel",
    "think_noise": "gumbel",
    "ouch_noise": "gumbel",
    "idle_noise": "gumbel"
  },
  "title_for_player": "Momma Meat Wizard",
  "territories": {
    "The Big Rock": {
      "vibe": "immovable, judgmental, slightly warm",
      "bonus": {
        "courage": 3
      },
      "faction_bonus": "Bonk Battalion"
    },
    "The Loud Bush": {
      "vibe": "rustles aggressively for no reason",
      "bonus": {
        "curiosity": 4
      },
      "faction_bonus": "Chaos Choir"
    },
    "The Shiny Pit": {
      "vibe": "glimmers ominously, hums in F#",
      "bonus": {
        "loyalty": 3
      },
      "faction_bonus": "Shiny Seekers"
    },
    "The Moss Blanket": {
      "vibe": "soft, damp, emotionally supportive",
      "bonus": {
        "wisdom": 5
      },
      "faction_bonus": "Moss Goblins"
    },
    "The Unreasonable Clearing": {
      "vibe": "geometry makes no sense here",
      "bonus": {
        "masochism": 2
      },
      "faction_bonus": "The Unreasonable Ones"
    },
    "The Screaming Meadow": {
      "vibe": "the grass yells compliments",
      "bonus": {
        "power": 3
      },
      "faction_bonus": null
    }
  },
  "items": {
    "Cursed Spoon": {
      "effect": {
        "wisdom": -2,
        "curiosity": 4
      },
      "vibe": "it vibrates ominously"
    },
    "Shiny Pebble": {
      "effect": {
        "loyalty": 3
      },
      "vibe": "glimmers with suspicious enthusiasm"
    },
    "Angry Stick": {
      "effect": {
        "aggression": 4
      },
      "vibe": "seems upset about something"
    },
    "Moss Cube": {
      "effect": {
        "wisdom": 3,
        "anxiety": -2
      },
      "vibe": "soft, damp, cube-shaped"
    },
    "Goblin Tooth (Probably)": {
      "effect": {
        "courage": 2
      },
      "vibe": "warm… too warm"
    },
    "Forbidden Berry": {
      "effect": {
        "power": 3,
        "wisdom": -1
      },
      "vibe": "glows faintly"
    },
    "Screaming Pebble": {
      "effect": {
        "anxiety": 3
      },
      "vibe": "yells when touched"
    },
    "Pocket Void": {
      "effect": {
        "curiosity": 5,
        "loyalty": -2
      },
      "vibe": "a tiny portable nothingness"
    },
    "Bent Fork of Destiny": {
      "effect": {
        "power": 4
      },
      "vibe": "crooked but confident"
    },
    "Suspicious Egg": {
      "effect": {
        "masochism": 2
      },
      "vibe": "it wiggles occasionally"
    },
    "Haunted Leaf": {
      "effect": {
        "anxiety": 2,
        "wisdom": 1
      },
      "vibe": "rustles even indoors"
    },
    "Shiny Rock (Extra Shiny)": {
      "effect": {
        "loyalty": 5
      },
      "vibe": "blindingly fabulous"
    },
    "Goblin Coupon": {
      "effect": {
        "courage": 1
      },
      "vibe": "expired decades ago"
    },
    "Wiggly Stick": {
      "effect": {
        "curiosity": 2
      },
      "vibe": "wiggles on its own schedule"
    },
    "Bone of Unknown Origin": {
      "effect": {
        "power": 2,
        "anxiety": 1
      },
      "vibe": "mysterious and rude"
    },
    "Soggy Sock": {
      "effect": {
        "masochism": 3
      },
      "vibe": "wet. always wet."
    },
    "Miniature Door": {
      "effect": {
        "wisdom": 2
      },
      "vibe": "leads nowhere but feels important"
    },
    "Sparkling Dust": {
      "effect": {
        "loyalty": 1,
        "curiosity": 1
      },
      "vibe": "gets everywhere"
    },
    "Goblin Trading Card": {
      "effect": {
        "courage": 2
      },
      "vibe": "rare holographic edition"
    },
    "Suspicious Cube": {
      "effect": {
        "power": 1,
        "curiosity": 3
      },
      "vibe": "buzzes like it knows secrets"
    }
  },
  "name_start": [
    "Scr",
    "Blib",
    "Bonk",
    "Grub",
    "Snar",
    "Plib",
    "Krub",
    "Yib",
    "Trun",
    "Mog",
    "Wib",
    "Frub",
    "Glo",
    "Spro",
    "Nib",
    "Zag",
    "Dro",
    "Clum",
    "Bree",
    "Hog"
  ],
  "name_end": [
    "blo",
    "bble",
    "dunk",
    "glo",
    "fip",
    "wunk",
    "sprag",
    "mop",
    "doodle",
    "snip",
    "gunk",
    "wobble",
    "florp",
    "snorf",
    "tunk",
    "zibble",
    "crunk"
  ],
  "factions": [
    "Moss Goblins",
    "Shiny Seekers",
    "Chaos Choir",
    "Bonk Battalion",
    "Mushroom Union"
  ],
  "dialogue": {
    "fight": [
      "square up, leaf boy!",
      "I challenge thee to a BONK-OFF!",
      "prepare for maximum slapstick!",
      "violence but silly!",
      "I swing with the power of poor decisions!"
    ],
    "defeat": [
      "I have been bonked… emotionally.",
      "the air cheated!",
      "I fall with dramatic flair!",
      "I regret everything!",
      "ow. my pride. and my face."
    ],
    "victory": [
      "I am the bonk champion!",
      "witness my chaotic glory!",
      "I win! I win! I win!",
      "the prophecy foretold my triumph!",
      "SKREEEEE victory screech!"
    ],
    "rivalry": [
      "your face is symmetrical and I hate it!",
      "you smell like reasonable decisions!",
      "I bite you but gently!",
      "your vibes are uneven!",
      "you look like a mossless rock!"
    ],
    "general": [
      "wooOOOAAAHH buddy!!",
      "I did a bad thing on purpose.",
      "I found a shiny and now I'm emotionally attached.",
      "I am speed. But only emotionally.",
      "I have made a choice and it was wrong.",
      "the moon owes me rent.",
      "your shadow tastes like questions.",
      "time tripped over itself again.",
      "the sky blinked at me twice.",
      "I saw a dream fall out of a tree.",
      "SKREEEEEE.",
      "bonk bonk BONK.",
      "I crave chaos and soup.",
      "I ate a rock and now I know secrets.",
      "I am the chair now."
    ],
    "greeting": [
      "hi {title}!! I missed your vibes.",
      "{title}, the forest screamed your name again.",
      "behold! I have arrived to cause problems.",
      "{title}, I have concerns. Mostly about me.",
      "the moss whispered you were coming."
    ],
    "item": [
      "SHINY ACQUIRED: {item}!",
      "this {item} concerns me deeply.",
      "I licked the {item}. it is mine now.",
      "the {item} whispered at me."
    ],
    "think": [
      "thinks very hard about nothing."
    ],
    "ouch": [
      "pokes themselves experimentally."
    ],
    "idle": [
      "stands still, overwhelmed."
    ],
    "dream": [
      "drifts through soft colors.",
      "relives something confusing."
    ],
    "catchphrase": [
      "shiny time.",
      "I crave chaos and soup.",
      "bonk bonk BONK."
    ],
    "crush": [
      "your voice makes my brain do flips.",
      "I collected a shiny for you.",
      "I think you are sparkly.",
      "I wrote a poem about you but then I ate it."
    ],
    "hug": [
      "softness acquired.",
      "hugs you back with chaotic enthusiasm."
    ],
    "praise": [
      "I am a bean??",
      "wiggles proudly.",
      "beams with chaotic joy."
    ]
  },
  "keywords": {
    "positive": [
      "love",
      "good",
      "nice",
      "friend",
      "thanks",
      "happy"
    ],
    "negative": [
      "hate",
      "bad",
      "stupid",
      "ugly",
      "hurt",
      "angry"
    ],
    "friend": [
      "friend"
    ]
  },
  "release": "2.0",
  "compatible_v1_hashes": [
    "185a8912ae6181f0fa61068d967e1459edc63ffcb0248d1a473b010cdf56ed71"
  ],
  "culture": {
    "max_words": 256,
    "max_phrases": 64,
    "max_links": 768,
    "max_sentence_words": 14,
    "innovation_chance": 0.12,
    "learned_speech_chance": 0.85,
    "reflection_chance": 0.25,
    "conversation_chance": 0.9,
    "thought_history": 12
  },
  "society": {
    "apprentice_words": 1,
    "apprentice_conversations": 1,
    "storyteller_words": 3,
    "storyteller_conversations": 3,
    "graduate_words": 12,
    "graduate_conversations": 6,
    "partner_threshold": 18,
    "bond_chance": 0.35,
    "colony_min_members": 2,
    "colony_prefixes": [
      "Moss",
      "Shiny",
      "Moon",
      "Soup",
      "Dream",
      "Pebble"
    ],
    "colony_suffixes": [
      "Nest",
      "Grove",
      "Cuddle Commune",
      "Choir",
      "Garden"
    ],
    "colony_join_threshold": 4,
    "affection_gain": 3,
    "affection_decay": 0.999,
    "chronicle_limit": 256
  }
}

// LonkWorld XC application 1.0.
// Edit the application declaration above to change names, dialogue and world content.
// Edit this native xembra model to change emotional dynamics and behavior.
// Single-field updates below are lowered to ordered XC vector updates by the host.
// Host random inputs use the saved world's seeded RNG; the XC model is deterministic
// for those inputs. Gumbel noise + argmax produces stochastic action selection.

xembra LonkMind version 1.0 {
  seed = 2026
  state Psi {
    energy: real = 0.5
    expectation: real = 0.5
    arousal: real = 0.2
    valence: real = 0.3
    error: real = 0.1
    power: real = 50
    courage: real = 50
    wisdom: real = 50
    masochism: real = 0
    joy: real = 50
    anxiety: real = 50
    aggression: real = 50
    curiosity: real = 50
    worry: real = 50
    loyalty: real = 50
    trauma: real = 0
    dopamine: real = 50
    sensory: real = 0.5
    arousal_noise: real = 0
    energy_noise: real = 0
    attack_noise: real = 0
    explore_noise: real = 0
    think_noise: real = 0
    ouch_noise: real = 0
    idle_noise: real = 0
    trauma_enabled: real = 1
  }
  memory Episodes {
    capacity = 24
    decay = 0.06
    top_k = 4
    similarity_weight = 0.3
    salience_weight = 0.4
    recency_weight = 0.3
  }
  observation Moment {
    vector = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    salience = 0.4
  }
  observation Kindness {
    vector = [0,0,0,0.12,-0.05,0,0,0,0,3,-2,0,0,-1,2,0,2,0,0,0,0,0,0,0,0,0]
    salience = 0.75
  }
  observation Threat {
    vector = [0,0,0.15,-0.1,0.15,0,-1,0,0,-2,3,0,0,2,0,1,0,0,0,0,0,0,0,0,0,0]
    salience = 0.85
  }
  actions { ATTACK EXPLORE THINK OUCH IDLE }
  policy Instinct {
    score ATTACK = power / 100 + arousal + aggression / 100 + attack_noise
    score EXPLORE = courage / 100 + curiosity / 100 + joy / 200 + explore_noise
    score THINK = wisdom / 100 + (1 - error) + loyalty / 200 + think_noise
    score OUCH = masochism / 100 + error + worry / 100 + ouch_noise
    score IDLE = 0.3 + (1 - energy) + anxiety / 200 + idle_noise
    select argmax
  }
  cycle {
    error <- clamp(error * 0.95, 0, 1)
    arousal <- clamp(arousal + 0.1 * (sensory - arousal) + 0.2 * arousal_noise, 0, 1)
    valence <- clamp(valence + 0.1 * (1 - error) - 0.05 * arousal + 0.02 * recall_signal("Episodes", "Kindness") - 0.02 * recall_signal("Episodes", "Threat"), 0, 1)
    energy <- clamp(energy + 0.1 * (valence - energy) + 0.05 * energy_noise, 0, 1)
    expectation <- clamp(expectation + 0.05 * (energy - expectation), 0, 1)
    power <- 100 * energy
    courage <- 100 * (1 - norm([energy - expectation]))
    wisdom <- 100 * (1 - error)
    masochism <- 100 * arousal
    joy <- clamp(0.9 * joy + 10 * valence, 0, 100)
    anxiety <- clamp(0.9 * anxiety + 10 * error, 0, 100)
    action <- Instinct(Psi)
  }
  event Tick { observe Moment cycle 1 }
  event birth { observe Moment remember Episodes }
  event hear_player { observe Moment remember Episodes }
  event hear { observe Moment remember Episodes }
  event hear_positive {
    observe Kindness
    joy <- clamp(joy + 3, 0, 100)
    valence <- clamp(valence + 0.08, 0, 1)
    error <- clamp(error - 0.03, 0, 1)
    remember Episodes
  }
  event hear_negative {
    observe Threat
    anxiety <- clamp(anxiety + 3, 0, 100)
    error <- clamp(error + 0.08, 0, 1)
    worry <- clamp(worry + 1, 0, 100)
    remember Episodes
  }
  event hear_friend { observe Kindness loyalty <- clamp(loyalty + 2, 0, 100) remember Episodes }
  event attack { observe Moment aggression <- clamp(aggression + 2, 0, 100) dopamine <- clamp(dopamine + 5, 0, 100) }
  event explore { observe Moment curiosity <- clamp(curiosity + 2, 0, 100) }
  event think { observe Moment wisdom <- clamp(wisdom + 2, 0, 100) error <- clamp(error - 0.02, 0, 1) }
  event ouch {
    observe Threat
    error <- clamp(error + 0.1, 0, 1)
    arousal <- clamp(arousal + 0.03, 0, 1)
    trauma <- clamp(trauma + 2 * trauma_enabled, 0, 100)
    remember Episodes
  }
  event idle { observe Moment energy <- clamp(energy + 0.03, 0, 1) arousal <- clamp(arousal - 0.02, 0, 1) }
  event territory { observe Moment remember Episodes }
  event find_item { observe Moment dopamine <- clamp(dopamine + 3, 0, 100) remember Episodes }
  event win_duel { observe Moment aggression <- clamp(aggression + 2, 0, 100) power <- clamp(power + 3, 0, 100) }
  event lose_duel { observe Threat worry <- clamp(worry + 2, 0, 100) courage <- clamp(courage - 2, 0, 100) }
  event hurt {
    observe Threat
    error <- clamp(error + 0.15, 0, 1)
    arousal <- clamp(arousal + 0.045, 0, 1)
    trauma <- clamp(trauma + trauma_enabled, 0, 100)
    remember Episodes
  }
  event social { observe Kindness loyalty <- clamp(loyalty + 2, 0, 100) joy <- clamp(joy + 1, 0, 100) }
  event nightmare { observe Threat worry <- clamp(worry + 5, 0, 100) courage <- clamp(courage - 5, 0, 100) trauma <- clamp(trauma - 5, 0, 100) remember Episodes }
  event dream { observe Kindness dopamine <- clamp(dopamine + 10, 0, 100) loyalty <- clamp(loyalty + 3, 0, 100) trauma <- clamp(trauma - 5, 0, 100) remember Episodes }
}

// XC Procedures 1: executable Lonk algorithms, interpreted without Python eval/exec.
procedures LonkWorld version 1 {
  namespace language {
    // Small learned word-association culture, not semantic understanding.
    // 
    // All persistent data is JSON; all random choices use the world's saved RNG.
    // Internal rehearsal reinforces associations without increasing outside exposure.
    let _COUNT <- 1000000;
    let _DEFAULTS <- {'max_words': 256, 'max_phrases': 64, 'max_links': 768, 'max_sentence_words': 14, 'innovation_chance': 0.12};
    let _CAPS <- {'max_words': 256, 'max_phrases': 64, 'max_links': 768, 'max_sentence_words': 32};
    let _TOKEN <- re.compile("[\\w']+", re.UNICODE);
    fn initial_language() {
      return {'version': 1, 'tokens': {}, 'bigrams': {}, 'phrases': [], 'origins': {}, 'dialect': {}, 'innovations': {}, 'total_heard': 0, 'total_spoken': 0, 'reflections': 0};
    }
    fn _settings(lonk) {
      let raw <- lonk.world.config.get('culture', {});
      let raw <- raw if isinstance(raw, dict) else {};
      let result <- {};
      for (key, default) in _DEFAULTS.items() {
        let value <- raw.get(key, default);
        if type(value) not in (int, float) or not math.isfinite(value) {
          let value <- default;
        }
        let result[key] <- max(0.0, min(1.0, value)) if key == 'innovation_chance' else max(1, min(_CAPS[key], int(value)));
      }
      return result;
    }
    fn _words(message) {
      return [word[:40] for word in _TOKEN.findall(str(message)[:500].lower())][:100];
    }
    fn _bump(table, key) {
      let table[key] <- min(_COUNT, table.get(key, 0) + 1);
    }
    fn _prune(state, settings) {
      let tokens <- state['tokens'];
      while len(tokens) > settings['max_words'] {
        remove tokens[min(tokens, key=tokens.get)];
      }
      for name in ('origins', 'dialect', 'innovations') {
        let state[name] <- {key: value for key, value in state[name].items() if key in tokens};
      }
      let links <- {a: {b: count for b, count in row.items() if b in tokens} for a, row in state['bigrams'].items() if a in tokens};
      let links <- {a: row for a, row in links.items() if row};
      let edges <- [(count, a, b) for a, row in links.items() for b, count in row.items()];
      for (_, a, b) in sorted(edges, key=lambda edge: edge[0])[:max(0, len(edges) - settings['max_links'])] {
        remove links[a][b];
      }
      let state['bigrams'] <- {a: row for a, row in links.items() if row};
      let state['phrases'] <- state['phrases'][-settings['max_phrases']:];
    }
    fn learn(lonk, message, speaker_id='player', internal=false) {
      // Learn words and directed transitions; never trigger another creature.
      let state <- lonk.linguistics;
      let words <- _words(message);
      if not words {
        return;
      }
      let settings <- _settings(lonk);
      let source <- str(speaker_id)[:80];
      for word in words {
        _bump(state['tokens'], word);
        state['origins'].setdefault(word, source);
        if word not in state['dialect'] {
          let state['dialect'][word] <- lonk.world.rng.randint(1, 5);
        }
      }
      for (a, b) in zip(words, words[1:]) {
        _bump(state['bigrams'].setdefault(a, {}), b);
      }
      if not internal {
        let state['total_heard'] <- min(_COUNT, state['total_heard'] + 1);
        let phrase <- ' '.join(words[:settings['max_sentence_words']]);
        if phrase in state['phrases'] {
          state['phrases'].remove(phrase);
        }
        state['phrases'].append(phrase);
      }
      _prune(state, settings);
    }
    fn _choose(rng, weighted) {
      let total <- sum((weight for _, weight in weighted));
      let draw <- rng.randrange(total);
      for (item, weight) in weighted {
        let draw <- draw - weight;
        if draw < 0 {
          return item;
        }
      }
      raise ValueError('Empty language choice');
    }
    fn _innovate(lonk, word) {
      let (state, rng) <- (lonk.linguistics, lonk.world.rng);
      let known <- list(state['tokens']);
      if len(word) < 2 {
        return word;
      }
      let other <- rng.choice(known);
      if other != word and len(other) > 1 {
        let result <- (word[:max(1, len(word) // 2)] + other[len(other) // 2:])[:40];
        let bases <- [word, other];
      }
      else {
        let index <- rng.randrange(len(word));
        let result <- (word[:index] + rng.choice('aeiou') + word[index + 1:])[:40];
        let bases <- [word];
      }
      if result == word or result in state['tokens'] {
        return word;
      }
      let state['innovations'][result] <- bases;
      let state['origins'][result] <- str(lonk.uid)[:80];
      let state['tokens'][result] <- 1;
      let state['dialect'][result] <- 5;
      if word in state['bigrams'] {
        let state['bigrams'][result] <- dict(state['bigrams'][word]);
      }
      return result;
    }
    fn compose(lonk, prompt=null, internal=false) {
      // Recombine learned transitions, with occasional jumps and pronunciation drift.
      // 
      // total_spoken counts generated outward utterances; callers should invoke this
      // only when speech is enabled. Explicit scripted speech is counted by callers.
      // 
      let (state, rng) <- (lonk.linguistics, lonk.world.rng);
      if not state['tokens'] {
        return null;
      }
      let settings <- _settings(lonk);
      let overlap <- list(dict.fromkeys((w for w in _words(prompt or '') if w in state['tokens'])));
      let candidates <- overlap or list(state['tokens']);
      fn weighted(words) {
        return [(w, max(1, int(math.sqrt(state['tokens'][w]))) * state['dialect'][w]) for w in words];
      }
      let word <- _choose(rng, weighted(candidates));
      let length <- rng.randint(min(3, settings['max_sentence_words']), settings['max_sentence_words']);
      let sentence <- [word];
      for _ in range(length - 1) {
        let row <- state['bigrams'].get(word, {});
        if row and rng.random() < 0.78 {
          let word <- _choose(rng, [(w, count * state['dialect'][w]) for w, count in row.items()]);
        }
        else {
          let word <- _choose(rng, weighted(list(state['tokens'])));
        }
        sentence.append(word);
      }
      if rng.random() < settings['innovation_chance'] {
        let index <- rng.randrange(len(sentence));
        let sentence[index] <- _innovate(lonk, sentence[index]);
      }
      let text <- ' '.join(sentence);
      if text in state['phrases'] or text == ' '.join(_words(prompt or '')) {
        let alternatives <- [w for w in state['tokens'] if w != sentence[-1]];
        if alternatives {
          let sentence[-1] <- _choose(rng, weighted(alternatives));
          let text <- ' '.join(sentence);
        }
      }
      if not internal {
        let state['total_spoken'] <- min(_COUNT, state['total_spoken'] + 1);
      }
      _prune(state, settings);
      return text;
    }
    fn reflect(lonk) {
      let thought <- compose(lonk, internal=true);
      if thought {
        learn(lonk, thought, speaker_id=lonk.uid, internal=true);
        let lonk.linguistics['reflections'] <- min(_COUNT, lonk.linguistics['reflections'] + 1);
      }
      return thought;
    }
    fn inherit(parent, baby) {
      // Copy culture/origins, reset heard/spoken/reflection developmental counters.
      // 
      // Association frequencies remain cultural evidence, not the baby's experience.
      // Personal preferences are rerolled so descendants develop their own voice.
      // 
      let baby.linguistics <- copy.deepcopy(parent.linguistics);
      for key in ('total_heard', 'total_spoken', 'reflections') {
        let baby.linguistics[key] <- 0;
      }
      let baby.linguistics['dialect'] <- {w: baby.world.rng.randint(1, 5) for w in baby.linguistics['tokens']};
      _prune(baby.linguistics, _settings(baby));
    }
    fn summary(lonk) {
      let state <- lonk.linguistics;
      return f"{len(state['tokens'])} words · {state['total_heard']} heard · {state['reflections']} thoughts · {len(state['innovations'])} inventions";
    }
    fn validate_state(state) {
      // Raise ValueError for malformed/unbounded saved language; return True.
      fn require(condition) {
        if not condition {
          raise ValueError('Invalid learned language state');
        }
      }
      fn token(value) {
        return isinstance(value, str) and 0 < len(value) <= 40 and (_TOKEN.fullmatch(value) is not null);
      }
      fn count(value, low=0, high=_COUNT) {
        return type(value) is int and low <= value <= high;
      }
      require(type(state) is dict and set(state) == set(initial_language()));
      require(type(state['version']) is int and state['version'] == 1);
      for key in ('total_heard', 'total_spoken', 'reflections') {
        require(count(state[key]));
      }
      for key in ('tokens', 'bigrams', 'origins', 'dialect', 'innovations') {
        require(type(state[key]) is dict and len(state[key]) <= 256);
      }
      let tokens <- state['tokens'];
      require(all((token(w) and count(n, 1) for w, n in tokens.items())));
      require(set(state['origins']) == set(tokens) == set(state['dialect']));
      require(all((isinstance(s, str) and len(s) <= 80 for s in state['origins'].values())));
      require(all((count(n, 1, 5) for n in state['dialect'].values())));
      let links <- 0;
      for (word, row) in state['bigrams'].items() {
        require(word in tokens and type(row) is dict and (0 < len(row) <= 256));
        require(all((w in tokens and count(n, 1) for w, n in row.items())));
        let links <- links + len(row);
      }
      require(links <= 768);
      require(type(state['phrases']) is list and len(state['phrases']) <= 64);
      require(all((isinstance(p, str) and 0 < len(p) <= 1311 and (0 < len(p.split()) <= 32) and all((token(w) for w in p.split())) for p in state['phrases'])));
      for (word, bases) in state['innovations'].items() {
        require(word in tokens and type(bases) is list and (1 <= len(bases) <= 2));
        require(all((token(w) for w in bases)));
      }
      return true;
    }
    fn validate(lonk) {
      return validate_state(lonk.linguistics);
    }
  }
  namespace society {
    // Finite social development, mutual affection and persistent little communities.
    let DEFAULTS <- {'apprentice_words': 1, 'storyteller_words': 3, 'apprentice_conversations': 1, 'storyteller_conversations': 3, 'graduate_words': 12, 'graduate_conversations': 6, 'partner_threshold': 18, 'bond_chance': 0.35, 'colony_min_members': 2, 'colony_prefixes': ['Moss', 'Shiny', 'Moon'], 'colony_suffixes': ['Nest', 'Grove', 'Cuddle Commune'], 'colony_join_threshold': 4, 'affection_gain': 3, 'affection_decay': 0.999, 'chronicle_limit': 256, 'familiar_friend_chance': 0.7};
    fn _number(world, key, low=0, high=1000000) {
      let value <- world.config.get('society', {}).get(key, DEFAULTS[key]);
      if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)) {
        let value <- DEFAULTS[key];
      }
      return max(low, min(high, value));
    }
    fn init_world(world) {
      let world.colonies <- {};
      let world.chronicle <- [];
      let world.next_colony_id <- 1;
    }
    fn init_lonk(lonk) {
      let lonk.social <- {'stage': 'hatchling', 'graduated_at': null, 'colony_id': null, 'partners': [], 'affection': {}, 'conversations': 0, 'thoughts': [], 'player_affection': 0, 'parents': []};
    }
    fn _record(world, text, kind, lonks=()) {
      world.chronicle.append({'tick': world.tick, 'kind': kind, 'text': text[:500], 'lonks': [x.uid for x in lonks]});
      remove world.chronicle[:-int(_number(world, 'chronicle_limit', 1, 1024))];
      for lonk in lonks {
        lonk.remember(text);
      }
      print(text);
    }
    fn on_hear(lonk, speaker=null, player=false) {
      if not lonk.alive {
        return;
      }
      let social <- lonk.social;
      let social['conversations'] <- min(1000000, social['conversations'] + 1);
      let gain <- _number(lonk.world, 'affection_gain', 0, 100);
      if player {
        let social['player_affection'] <- min(100, social['player_affection'] + gain);
      }
      if speaker is not null and speaker is not lonk and speaker.alive {
        let affinity <- social['affection'];
        let affinity[speaker.uid] <- min(100, affinity.get(speaker.uid, 0) + gain);
        maybe_bond(lonk, speaker);
      }
    }
    fn maybe_bond(a, b) {
      if a is b or not a.alive or (not b.alive) or (a.world is not b.world) {
        return false;
      }
      if b.uid in a.social['partners'] {
        return false;
      }
      let threshold <- _number(a.world, 'partner_threshold', 0, 100);
      if min(a.social['affection'].get(b.uid, 0), b.social['affection'].get(a.uid, 0)) < threshold {
        return false;
      }
      if a.world.rng.random() >= _number(a.world, 'bond_chance', 0, 1) {
        return false;
      }
      a.social['partners'].append(b.uid);
      if a.uid not in b.social['partners'] {
        b.social['partners'].append(a.uid);
      }
      _record(a.world, f'{a.name} and {b.name} become sweethearts and share a happy cuddle.', 'partnership', (a, b));
      return true;
    }
    fn develop(lonk) {
      if not lonk.alive {
        return;
      }
      let (social, world) <- (lonk.social, lonk.world);
      if social['graduated_at'] is not null {
        let social['stage'] <- 'graduate';
        return;
      }
      let words <- len(getattr(lonk, 'linguistics', {}).get('tokens', lonk.vocabulary));
      if words >= _number(world, 'graduate_words') and social['conversations'] >= _number(world, 'graduate_conversations') {
        let social['stage'] <- 'graduate';
        let social['graduated_at'] <- world.tick;
        _record(world, f'{lonk.name} graduates! A little storyteller is ready to help a colony grow.', 'graduation', (lonk,));
      }
      else {
        if words >= _number(world, 'storyteller_words') and social['conversations'] >= _number(world, 'storyteller_conversations') {
          let social['stage'] <- 'storyteller';
        }
        else {
          if words >= _number(world, 'apprentice_words') and social['conversations'] >= _number(world, 'apprentice_conversations') {
            let social['stage'] <- 'apprentice';
          }
        }
      }
    }
    fn _compatible(a, b) {
      return min(a.social['affection'].get(b.uid, 0), b.social['affection'].get(a.uid, 0)) >= _number(a.world, 'colony_join_threshold', 0, 100);
    }
    fn _name(world, key) {
      let options <- world.config.get('society', {}).get(key, DEFAULTS[key]);
      if not isinstance(options, list) {
        let options <- DEFAULTS[key];
      }
      let options <- [x[:80] for x in options if isinstance(x, str) and x.strip()];
      return world.rng.choice(options or DEFAULTS[key]);
    }
    fn society_tick(world) {
      // One reciprocal conversation per community; all loops are population bounded.
      let living <- [x for x in world.lonks if x.alive];
      let by_uid <- {x.uid: x for x in living};
      let decay <- _number(world, 'affection_decay', 0, 1);
      for lonk in living {
        let lonk.social['affection'] <- {uid: score * decay for uid, score in lonk.social['affection'].items() if uid in by_uid and uid != lonk.uid};
        let lonk.social['partners'] <- [uid for uid in lonk.social['partners'] if uid in by_uid];
      }
      for (cid, colony) in world.colonies.items() {
        let colony['members'] <- [x.uid for x in living if x.social['colony_id'] == cid];
        if not colony['members'] and colony['archived_at'] is null {
          let colony['archived_at'] <- world.tick;
        }
      }
      let groups <- {};
      for lonk in living {
        let cid <- lonk.social['colony_id'];
        if cid not in world.colonies or world.colonies[cid]['archived_at'] is not null {
          let _assigned_132 <- null;
          let lonk.social['colony_id'] <- _assigned_132;
          let cid <- _assigned_132;
        }
        groups.setdefault(cid, []).append(lonk);
      }
      for members in groups.values() {
        if len(members) < 2 {
          continue;
        }
        let chance <- world.config.get('culture', {}).get('conversation_chance', 0.9);
        if type(chance) not in (int, float) or not math.isfinite(chance) {
          let chance <- 0.9;
        }
        if world.rng.random() >= max(0, min(1, chance)) {
          continue;
        }
        let a <- world.rng.choice(members);
        let others <- [x for x in members if x is not a];
        let b <- max(others, key=lambda x: a.social['affection'].get(x.uid, 0)) if world.rng.random() < _number(world, 'familiar_friend_chance', 0, 1) else world.rng.choice(others);
        if a.territory != b.territory {
          print(f'{a.name} visits {b.name} for a little conversation.');
        }
        a.speak(target=b);
        b.speak(target=a);
      }
      for lonk in living {
        develop(lonk);
      }
      for lonk in living {
        if lonk.social['colony_id'] is not null or lonk.social['graduated_at'] is null {
          continue;
        }
        let colony <- next((c for c in world.colonies.values() if c['archived_at'] is null and any((_compatible(lonk, by_uid[uid]) for uid in c['members'] if uid in by_uid))), null);
        if colony is not null {
          let lonk.social['colony_id'] <- colony['id'];
          colony['members'].append(lonk.uid);
          _record(world, f"{lonk.name} joins {colony['name']}.", 'colony_join', (lonk,));
          continue;
        }
        let friends <- [x for x in living if x is not lonk and x.social['colony_id'] is null and (x.social['graduated_at'] is not null) and _compatible(lonk, x)];
        let minimum <- int(_number(world, 'colony_min_members', 2, 1000));
        if len(friends) + 1 < minimum {
          continue;
        }
        let founders <- [lonk] + friends[:minimum - 1];
        let cid <- f'colony-{world.next_colony_id}';
        let world.next_colony_id <- world.next_colony_id + 1;
        let name <- f"{_name(world, 'colony_prefixes')} {_name(world, 'colony_suffixes')}";
        let world.colonies[cid] <- {'id': cid, 'name': name, 'founded_at': world.tick, 'founders': [x.uid for x in founders], 'members': [x.uid for x in founders], 'archived_at': null};
        for member in founders {
          let member.social['colony_id'] <- cid;
        }
        _record(world, f"{' and '.join((x.name for x in founders))} found {name}!", 'colony_founded', founders);
      }
      let archived <- [cid for cid, c in world.colonies.items() if c['archived_at'] is not null];
      for cid in archived[:-64] {
        remove world.colonies[cid];
      }
    }
    fn inherit(parent, baby) {
      init_lonk(baby);
      let baby.social['parents'] <- [parent.uid];
      let baby.social['colony_id'] <- parent.social['colony_id'];
      let colony <- baby.world.colonies.get(baby.social['colony_id']);
      if colony is not null and baby.uid not in colony['members'] {
        colony['members'].append(baby.uid);
      }
    }
    fn on_departure(world, lonk) {
      for other in world.lonks {
        if other is not lonk and lonk.uid in other.social['partners'] {
          other.social['partners'].remove(lonk.uid);
          other.remember(f'I remember the happy cuddles I shared with {lonk.name}.');
        }
      }
      let lonk.social['partners'] <- [];
      let colony <- world.colonies.get(lonk.social['colony_id']);
      if colony is not null and lonk.uid in colony['members'] {
        colony['members'].remove(lonk.uid);
        if not colony['members'] {
          let colony['archived_at'] <- world.tick;
        }
      }
    }
    fn validate_world(world) {
      // Read-only persistence validation; historic founder/parent IDs may be absent.
      fn require(condition, message) {
        if not condition {
          raise ValueError(message);
        }
      }
      require(isinstance(world.colonies, dict) and isinstance(world.chronicle, list), 'Invalid society history');
      require(type(world.next_colony_id) is int and world.next_colony_id >= 1, 'Invalid colony sequence');
      for entry in world.chronicle {
        require(isinstance(entry, dict) and isinstance(entry.get('text'), str) and isinstance(entry.get('kind'), str) and isinstance(entry.get('lonks'), list) and (type(entry.get('tick')) is int) and (0 <= entry['tick'] <= world.tick), 'Invalid chronicle entry');
      }
      let by_uid <- {x.uid: x for x in world.lonks};
      for lonk in world.lonks {
        let social <- lonk.social;
        require(isinstance(social, dict) and set(init_keys()).issubset(social), 'Invalid social schema');
        require(social['stage'] in ('hatchling', 'apprentice', 'storyteller', 'graduate'), 'Invalid learning stage');
        require(type(social['conversations']) is int and social['conversations'] >= 0, 'Invalid conversation count');
        require(isinstance(social['affection'], dict), 'Invalid affection map');
        for score in list(social['affection'].values()) + [social['player_affection']] {
          require(type(score) in (int, float) and math.isfinite(score) and (0 <= score <= 100), 'Invalid affection');
        }
        for key in ('partners', 'parents', 'thoughts') {
          require(isinstance(social[key], list), f'Invalid {key}');
        }
        require(all((isinstance(uid, str) for uid in social['partners'] + social['parents'])), 'Invalid social ID');
        require(len(set(social['partners'])) == len(social['partners']), 'Duplicate partnership');
        for uid in social['partners'] {
          require(uid != lonk.uid and uid in by_uid and by_uid[uid].alive and lonk.alive, 'Invalid active partnership');
          require(lonk.uid in by_uid[uid].social['partners'], 'Nonreciprocal partnership');
        }
        let cid <- social['colony_id'];
        require(cid is null or (isinstance(cid, str) and cid in world.colonies), 'Unknown colony');
        if cid is not null {
          require(lonk.uid in world.colonies[cid]['members'], 'Missing colony membership');
        }
        let graduation <- social['graduated_at'];
        require(graduation is null or (type(graduation) is int and 0 <= graduation <= world.tick), 'Invalid graduation');
      }
      for (cid, colony) in world.colonies.items() {
        require(isinstance(cid, str) and cid.startswith('colony-') and cid[7:].isdigit() and (0 < int(cid[7:]) < world.next_colony_id), 'Invalid colony sequence reference');
        require(isinstance(colony, dict) and colony.get('id') == cid, 'Invalid colony identity');
        require(isinstance(colony.get('name'), str) and isinstance(colony.get('members'), list) and isinstance(colony.get('founders'), list), 'Invalid colony schema');
        require(all((isinstance(uid, str) for uid in colony['members'] + colony['founders'])), 'Invalid colony ID');
        require(len(set(colony['members'])) == len(colony['members']), 'Duplicate colony member');
        for uid in colony['members'] {
          require(uid in by_uid and by_uid[uid].social['colony_id'] == cid, 'Invalid colony member');
        }
        require(not colony['members'] or colony.get('archived_at') is null, 'Archived colony has members');
        for key in ('founded_at', 'archived_at') {
          let value <- colony.get(key);
          require(key == 'archived_at' and value is null or (type(value) is int and 0 <= value <= world.tick), 'Invalid colony date');
        }
      }
      return true;
    }
    fn init_keys() {
      return ('stage', 'graduated_at', 'colony_id', 'partners', 'affection', 'conversations', 'thoughts', 'player_affection', 'parents');
    }
  }
  namespace engine {
    // Finite, deterministic LonkWorld simulation and versioned JSON persistence.
    let SCHEMA <- 'lonkworld/2';
    let ACTIONS <- ('attack', 'explore', 'think', 'ouch', 'idle');
    let EMOTIONS <- ('power', 'courage', 'wisdom', 'masochism', 'joy', 'anxiety');
    let TRAITS <- ('aggression', 'curiosity', 'anxiety', 'loyalty');
    fn clamp(value, low=0.0, high=100.0) {
      let value <- float(value);
      if not math.isfinite(value) {
        raise ValueError('Simulation values must be finite');
      }
      return max(low, min(high, value));
    }
    fn bounded_append(sequence, value, limit=64) {
      sequence.append(value);
      remove sequence[:-limit];
    }
    record Lonk {
      // A creature whose references are IDs and whose memories are plain JSON data.
      fn init(self, world, name=null) {
        let self.world <- world;
        let self.uid <- f'lonk-{world.next_uid}';
        let world.next_uid <- world.next_uid + 1;
        let rng <- world.rng;
        let self.name <- name or rng.choice(world.config['name_start']) + rng.choice(world.config['name_end']);
        let self.state <- list(world.config['world']['initial_state']);
        let (low, high) <- world.config['world']['initial_stats'];
        let self.emotion <- {key: rng.randint(low, high) for key in EMOTIONS};
        let self.personality <- {key: rng.randint(low, high) for key in TRAITS};
        let self.habits <- {key: 0 for key in ACTIONS};
        let self.age <- 0;
        let self.lifespan <- rng.randint(*world.config['world']['lifespan']);
        let self.alive <- true;
        let self.generation <- 1;
        let self.territory <- rng.choice(list(world.config['territories']));
        let self.faction <- rng.choice(world.config['factions']);
        let self.inventory <- [];
        let self.relationships <- {};
        let self.memory <- {'player_words': {}, 'lonk_words': {}, 'word_counts': {}, 'rumors': [], 'events': [], 'player_interactions': []};
        let self.long_memory <- [];
        let self.trauma <- 0;
        let self.dopamine <- 50;
        let self.crush <- null;
        let self.catchphrase <- null;
        let self.rival <- null;
        let self.xc_checkpoint <- null;
        let self.linguistics <- language.initial_language();
        society.init_lonk(self);
        for _ in range(rng.randint(0, 2)) {
          self.inventory.append(rng.choice(list(world.config['items'])));
        }
      }
      property vocabulary(self) {
        return self.memory['word_counts'];
      }
      property language(self) {
        return self.memory['word_counts'];
      }
      property items(self) {
        return self.inventory;
      }
      fn normalize(self) {
        if len(self.state) != 5 {
          raise ValueError('Lonk state must contain five values');
        }
        let self.state <- [clamp(x, 0, 1) for x in self.state];
        for mapping in (self.emotion, self.personality) {
          for key in mapping {
            let mapping[key] <- clamp(mapping[key]);
          }
        }
        for key in self.habits {
          let self.habits[key] <- clamp(self.habits[key], 0, 1000);
        }
        let self.trauma <- clamp(self.trauma);
        let self.dopamine <- clamp(self.dopamine);
        for key in self.relationships {
          let self.relationships[key] <- clamp(self.relationships[key], -100, 100);
        }
        remove self.inventory[:-32];
        remove self.long_memory[:-128];
      }
      fn remember(self, message) {
        let event <- {'tick': self.world.tick, 'text': str(message)[:500]};
        if len(self.memory['events']) >= 64 {
          bounded_append(self.long_memory, self.memory['events'][0], 128);
        }
        bounded_append(self.memory['events'], event);
      }
      fn hear(self, message, speaker=null, player=false) {
        let message <- str(message)[:500];
        language.learn(self, message, speaker_id='player' if player else speaker.uid if speaker else 'world');
        society.on_hear(self, speaker=speaker, player=player);
        let counts <- self.memory['player_words' if player else 'lonk_words'];
        for word in re.findall("[\\w']+", message.lower())[:100] {
          for table in (counts, self.memory['word_counts']) {
            if word not in table and len(table) >= 256 {
              let oldest <- min(table, key=table.get);
              remove table[oldest];
            }
            let table[word] <- min(1000000, table.get(word, 0) + 1);
          }
        }
        self.remember(message);
        if player {
          bounded_append(self.memory['player_interactions'], {'tick': self.world.tick, 'text': message});
        }
        if self.world.toggles['gossip'] and message {
          if not any((r['text'] == message for r in self.memory['rumors'])) {
            bounded_append(self.memory['rumors'], {'text': message, 'source': speaker.uid if speaker else 'player', 'tick': self.world.tick}, 32);
          }
        }
        if speaker {
          self.update_relationship(speaker, 1);
        }
        self.world.event(self, 'hear_player' if player else 'hear');
        let words <- set(re.findall("[\\w']+", message.lower()));
        if words.intersection(self.world.config['keywords']['positive']) {
          self.world.event(self, 'hear_positive');
        }
        if words.intersection(self.world.config['keywords']['negative']) {
          self.world.event(self, 'hear_negative');
        }
        if words.intersection(self.world.config['keywords']['friend']) {
          self.world.event(self, 'hear_friend');
        }
      }
      fn speak(self, message=null, target=null, context='general', **values) {
        if not self.world.toggles['talk'] {
          return;
        }
        let generated <- false;
        if message is null and context == 'general' and (self.world.rng.random() < self.world.config['culture']['learned_speech_chance']) {
          let message <- language.compose(self);
          let generated <- message is not null;
        }
        let message <- message or self.world.line(context, **values);
        if not generated {
          let self.linguistics['total_spoken'] <- min(1000000, self.linguistics['total_spoken'] + 1);
        }
        print(f'{self.name}' + (f' -> {target.name}' if target else '') + f': {message}');
        let listeners <- [target] if target else self.world.neighbors(self);
        for other in listeners {
          if other is not self and other.alive {
            other.hear(message, self);
          }
        }
      }
      fn update_relationship(self, other, amount) {
        let affinity <- 3 if self.faction == other.faction else -1;
        let self.relationships[other.uid] <- clamp(self.relationships.get(other.uid, 0) + amount + affinity, -100, 100);
        if len(self.relationships) > self.world.max_population * 2 {
          let live_ids <- {x.uid for x in self.world.lonks};
          let self.relationships <- {k: v for k, v in self.relationships.items() if k in live_ids};
        }
      }
      fn register_pain(self, amount) {
        if self.world.controller is not null {
          self.world.event(self, 'hurt');
          return;
        }
        let self.state[4] <- clamp(self.state[4] + amount, 0, 1);
        let self.state[2] <- clamp(self.state[2] + 0.3 * amount, 0, 1);
        if self.world.toggles['trauma'] {
          let self.trauma <- clamp(self.trauma + amount * 100);
        }
      }
      fn perform_action(self, action) {
        let (world, rng) <- (self.world, self.world.rng);
        if action not in ACTIONS {
          raise ValueError(f'Controller returned unknown action: {action!r}');
        }
        if not world.toggles['violence'] and action in ('attack', 'ouch') {
          let action <- 'idle';
        }
        let self.habits[action] <- min(1000, self.habits[action] + 1);
        world.event(self, action);
        if action == 'attack' {
          let neighbors <- world.neighbors(self);
          if neighbors {
            let opponent <- min(neighbors, key=lambda other: self.relationships.get(other.uid, 0));
            self.duel(opponent);
          }
        }
        else {
          if action == 'explore' {
            let self.territory <- rng.choice(list(world.config['territories']));
            let territory <- world.config['territories'][self.territory];
            print(f"{self.name} wanders into {self.territory} -- {territory['vibe']}.");
            if world.controller is null {
              self.apply_effects(territory.get('bonus', {}));
            }
            world.event(self, 'territory');
            if rng.random() < world.config['world']['item_chance'] {
              let item <- rng.choice(list(world.config['items']));
              bounded_append(self.inventory, item, 32);
              if world.controller is null {
                self.apply_effects(world.config['items'][item].get('effect', {}));
              }
              world.event(self, 'find_item');
              self.speak(context='item', item=item);
            }
          }
          else {
            print(f'{self.name} {world.line(action)}');
            if world.controller is null {
              if action == 'think' {
                let self.emotion['wisdom'] <- self.emotion['wisdom'] + 2;
              }
              else {
                if action == 'ouch' {
                  self.register_pain(0.1);
                }
                else {
                  let self.state[0] <- self.state[0] + 0.03;
                }
              }
            }
          }
        }
        self.remember(action);
        self.normalize();
      }
      fn apply_effects(self, effects) {
        for (key, amount) in effects.items() {
          let table <- self.emotion if key in self.emotion else self.personality;
          if key in table {
            let table[key] <- table[key] + amount;
          }
        }
      }
      fn duel(self, opponent) {
        if not self.world.toggles['violence'] {
          return;
        }
        let self.rival <- opponent.uid;
        self.speak(context='fight', target=opponent);
        let winner <- self.world.rng.choice([self, opponent]);
        let loser <- opponent if winner is self else self;
        print(f'BONK! {winner.name} bonks {loser.name} with comedic force!');
        self.world.event(winner, 'win_duel');
        self.world.event(loser, 'lose_duel');
        if self.world.controller is null {
          loser.register_pain(0.15);
        }
        else {
          self.world.event(loser, 'hurt');
        }
        loser.update_relationship(winner, -12);
        winner.update_relationship(loser, -4);
        winner.speak(context='victory');
        loser.speak(context='defeat');
        if self.world.toggles['shinywars'] and loser.inventory {
          bounded_append(winner.inventory, loser.inventory.pop(), 32);
        }
        winner.normalize();
        loser.normalize();
      }
      fn dream(self) {
        let nightmare <- self.world.toggles['trauma'] and self.trauma > 20 and (self.world.rng.random() < 0.5);
        print(f"{self.name} {self.world.config['dialogue']['dream'][int(nightmare)]}");
        self.world.event(self, 'nightmare' if nightmare else 'dream');
        if self.world.controller is null {
          let self.personality['anxiety' if nightmare else 'loyalty'] <- self.personality['anxiety' if nightmare else 'loyalty'] + 3;
          let self.trauma <- max(0, self.trauma - 5);
        }
        self.remember('nightmare' if nightmare else 'dream');
        self.normalize();
      }
      fn rebirth(self) {
        let self.alive <- false;
        let baby <- Lonk(self.world);
        let baby.generation <- self.generation + 1;
        let baby.faction <- self.faction;
        let baby.territory <- self.territory;
        let mutation <- self.world.config['world']['inheritance_mutation'];
        let baby.personality <- {k: clamp(v + self.world.rng.randint(-mutation, mutation)) for k, v in self.personality.items()};
        let baby.memory['word_counts'] <- dict(sorted(self.vocabulary.items(), key=lambda item: -item[1])[:64]);
        let baby.long_memory <- copy.deepcopy((self.long_memory + self.memory['events'])[-24:]);
        let baby.memory['rumors'] <- copy.deepcopy(self.memory['rumors'][-8:]);
        language.inherit(self, baby);
        society.inherit(self, baby);
        self.world.event(baby, 'birth');
        print(f'{self.name} dissolves into dream-mist... A dream-egg hatches into {baby.name}! (Gen {baby.generation})');
        return baby;
      }
      fn respond_to_player(self, message) {
        let (rng, rules) <- (self.world.rng, self.world.config['world']);
        let words <- set(re.findall("[\\w']+", message.lower()));
        if self.crush is null and rng.random() < rules['crush_chance'] {
          let self.crush <- 'Player';
        }
        if self.catchphrase is null and rng.random() < rules['catchphrase_chance'] {
          let self.catchphrase <- self.world.line('catchphrase');
        }
        let learned <- language.compose(self, prompt=message);
        if self.crush == 'Player' {
          let reply <- self.world.line('crush') + (' ' + learned if learned else '');
        }
        else {
          if 'hug' in words {
            let reply <- self.world.line('hug');
          }
          else {
            if words.intersection(self.world.config['keywords']['positive']) {
              let reply <- self.world.line('praise');
            }
            else {
              if learned {
                let reply <- learned;
              }
              else {
                if self.long_memory and rng.random() < rules['recall_chance'] {
                  let reply <- str(rng.choice(self.long_memory).get('text', ''));
                }
                else {
                  let reply <- self.world.line('greeting');
                }
              }
            }
          }
        }
        return reply + (' ' + self.catchphrase if self.catchphrase and rng.random() < 0.3 else '');
      }
    }
    record LonkWorld {
      fn init(self, starting_population=5, max_population=20, controller=null, seed=2026) {
        if type(starting_population) is not int or type(max_population) is not int or (not 0 <= starting_population <= max_population) or (max_population < 1) {
          raise ValueError('Population must be integers with 0 <= starting_population <= max_population and max_population >= 1');
        }
        if controller is null {
          raise ValueError('An XC application controller is required.');
        }
        let self.controller <- controller;
        let self.source_hash <- controller.source_hash;
        let self.config <- copy.deepcopy(controller.config);
        let self.rng <- random.Random(seed);
        let self.next_uid <- 1;
        let self.tick <- 0;
        let self.max_population <- max_population;
        let self.toggles <- {'talk': true, 'violence': true, 'dreams': true, 'gossip': true, 'trauma': true, 'shinywars': false};
        let self.lonks <- [];
        society.init_world(self);
        for _ in range(starting_population) {
          let creature <- Lonk(self);
          self.lonks.append(creature);
          self.event(creature, 'birth');
        }
      }
      fn event(self, lonk, event_name) {
        if self.controller is not null and hasattr(self.controller, 'event') {
          self.controller.event(lonk, event_name);
          lonk.normalize();
        }
      }
      fn line(self, context='general', **values) {
        let pool <- self.config['dialogue'].get(context, self.config['dialogue']['general']);
        values.setdefault('title', self.config['title_for_player']);
        return self.rng.choice(pool).format(**values);
      }
      fn neighbors(self, lonk) {
        return [other for other in self.lonks if other is not lonk and other.alive and (other.territory == lonk.territory)];
      }
      fn player_say(self, message, target_uid=null) {
        if not isinstance(message, str) or not message.strip() {
          raise ValueError('Message must be nonempty text');
        }
        if not self.toggles['talk'] {
          print('Talking is currently paused.');
          return;
        }
        let listeners <- [x for x in self.lonks if x.alive and (target_uid is null or x.uid == target_uid)];
        if target_uid is not null and (not listeners) {
          raise ValueError(f'No living Lonk with ID {target_uid!r}');
        }
        let message <- message.strip()[:500];
        print(f'YOU say: {message}');
        for lonk in listeners {
          lonk.hear(message, player=true);
          if self.toggles['talk'] {
            print(f'{lonk.name} -> YOU: {lonk.respond_to_player(message)}');
          }
        }
      }
      fn world_tick(self) {
        let self.tick <- self.tick + 1;
        print(f'WORLD TICK {self.tick}');
        let babies <- [];
        for lonk in list(self.lonks) {
          if not lonk.alive {
            continue;
          }
          let action <- self.controller.step(lonk);
          lonk.normalize();
          lonk.perform_action(action);
          let neighbors <- self.neighbors(lonk);
          if neighbors and self.rng.random() < self.config['world']['social_chance'] {
            let other <- self.rng.choice(neighbors);
            lonk.update_relationship(other, 2);
            other.update_relationship(lonk, 2);
            self.event(lonk, 'social');
            if self.toggles['gossip'] and lonk.memory['rumors'] {
              let rumor <- self.rng.choice(lonk.memory['rumors'])['text'];
              if self.rng.random() < self.config['world']['rumor_mutation_chance'] {
                let rumor <- (rumor + ' maybe')[:500];
              }
              if self.toggles['talk'] {
                lonk.speak(rumor, other);
              }
            }
          }
          if self.toggles['talk'] and self.rng.random() < self.config['world']['speech_chance'] {
            lonk.speak();
          }
          if self.toggles['dreams'] and self.rng.random() < self.config['world']['dream_chance'] {
            lonk.dream();
          }
          if self.rng.random() < self.config['culture']['reflection_chance'] {
            let thought <- language.reflect(lonk);
            if thought {
              bounded_append(lonk.social['thoughts'], {'tick': self.tick, 'text': thought}, self.config['culture']['thought_history']);
            }
          }
          for uid in lonk.relationships {
            let lonk.relationships[uid] <- lonk.relationships[uid] * self.config['world']['relationship_decay'];
          }
          let lonk.age <- lonk.age + 1;
          society.develop(lonk);
          if lonk.age >= lonk.lifespan {
            if self.rng.random() < self.config['world']['rebirth_chance'] {
              babies.append(lonk.rebirth());
            }
            else {
              let lonk.alive <- false;
              print(f'{lonk.name} poofs into sparkles at age {lonk.age}.');
            }
            society.on_departure(self, lonk);
          }
          lonk.normalize();
        }
        let self.lonks <- [lonk for lonk in self.lonks if lonk.alive];
        self.lonks.extend(babies[:max(0, self.max_population - len(self.lonks))]);
        if len(self.lonks) < self.max_population and self.rng.random() < self.config['world']['arrival_chance'] {
          let creature <- Lonk(self);
          self.lonks.append(creature);
          self.event(creature, 'birth');
          print(f'A wild Lonk appears: {creature.name}!');
        }
        society.society_tick(self);
      }
    }
  }
}
