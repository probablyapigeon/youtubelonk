# Civilization systems

Run the same Python command, then use `load` to continue a saved world. Existing
saves without civilization data start with fresh registries while retaining their
Lonks and vocabulary. New saves retain generated rooms, cultures, markets, factions,
relationships, schools, pending children, diffusion waves, and broker backing.

Everything runs locally with Python and NumPy. No LLM or API is involved.

## What triggers each system

| System | Default trigger | Actual effects |
| --- | --- | --- |
| Meme-splice | Two excited Lonks, same faction and sacred room; arousal >= .65, valence >= .45 | Combines weighted words and a room landmark into a named cultural canon; spreads vocabulary, changes Will and composable-action weights once per concept. |
| Annex | Four faction members in a base room share at least three content tokens | Creates a connected annex; moves up to two inhabitants while keeping three in the parent room. Annex inhabitants get one additional action per world tick. |
| Annex fuel | An annex occupant carries an egg or portal | Consumes one item per primary tick, permanently increases structural anxiety reduction by 2 (cap 40), and adds Power to the primary loop. |
| Semantic market | Item names are whispered, taught, or screamed | Updates a Beta-style attention estimate and bounded exponential price multiplier. Regular speech does not pump prices. Hot assets raise trade Will and attract seekers. |
| Resonant diffusion | The programmer edits the Chosen, or `/tune` edits its policy bias | Propagates the numerical parameter delta one graph frontier per primary tick, attenuated by distance. Each recipient gets a wave once. Control Twins are excluded. |
| Martyr cult | A Lonk dies and survivors have anxiety >= 65 or wisdom <= 35 | Locks final spoken words into the Holy Lexicon, forms a faction, and builds a shrine at the death location. Actual entry forces a holy scream or temporary trance. |
| Romance | Two Lonks share a room for four primary ticks with arousal >= .6 | Creates mutual crushes and per-partner affinity vectors. They follow each other and give their highest-priced available items; aggressive outsiders can trigger jealous gossip or a bonk. |
| Offspring | Mutual crushes have 100 Joy in the same supportive room | Queues a next-generation Lonk with a spliced name, averaged neural/emotional parameters, and balanced favorite-word selections when both parents have vocabulary. |
| School | Three same-faction occupants are in an outpost/city | The wisest becomes Headmaster. Each primary tick copies the Headmaster's dictionary, knowledge, axioms and existential question into students. |
| Extortion | High aggression (>=70), low loyalty (<=40), and an anxious owner (>=60) of a valuable item | Can prompt pursuit and intimidation trading. A successful scam exchanges real items and damages the victim's mood and relationship. Sanctuaries block extortion. |
| Settlement | Three occupants remain for five ticks, or >5 items are dropped there | Creates an outpost. Ten sustained ticks or >10 dropped items creates a city. Visits grant nonstacking health capacity, and city residence reduces anxiety. Local cultural canons produce laws. |

The cultural canons are **social beliefs**, separate from the existing empirical
axioms whose predictions are tested against outcomes. Canonization is not proof
that the belief is true. They appear in `/society` with their actual effects in
saved civilization data.

## Player controls

Use current names from `stats`. Multiword room names must be quoted; city display
names and the original room names both work.

```text
/society
/market
/observe Shump
/matchmake Flonk Plarp
/heartbreak Flonk the bees whispered betrayal
/blaspheme "The Shiny Pit" dad denies the bees
/subvert HEADMASTER_NAME pickle
/back Shump portal
/tax 0.1
/confiscate Shump "Warrior's Shield"
/drop Shump soggy sock
/engineer BABY_NAME explore 2
/tune CHOSEN_NAME explore 1.5
/interact Shump scream portal
/interact Shump extort Flip
```

- `/society` lists cultural concepts, generated locations, city laws, shrines and
  active Headmasters. `/observe` now lists items and coins.
- Quote phrases containing apostrophes when using the new broker/cult commands.
- `/subvert` gives the Headmaster a real bribe item and schedules the classroom to
  proclaim **I am Pickle Rick!** on each participant's next turn.
- `/back` is an endless *source*, not an infinitely growing inventory: a missing
  backed item is replenished once per world tick. The broker treasury retains
  confiscations and collects available coins from trades at the selected tax rate.
- `/engineer` edits one of the newborn's six policy-output biases through age 1.
  Use `idle`, `explore`, `think`, `attack`, `speak`, or `trade`, and a bias in [-5,5].
  The birth notice may precede arrival; wait for the child to enter the population.
- `/tune` edits the Chosen's bias and emits a diffusion wave. It rejects Control
  Twins. Automatic analytical programming emits waves through the same path.
- `/interact` now executes supported primitives. `scream portal` feeds the market;
  `extort Flip` requests a targeted intimidation attempt. Autonomous extortion
  still requires the personality/target conditions above.
- Teaching a phrase or a swear continues to work through `/say`. Physical gifts
  still work through `/gift`; objects remain real inventory that can be shared.

## Bounds and interpretation

- Annex scheduling is a bounded second pass, not recursion or a second thread.
  Two actions mean faster learning and ordinary resource use, but chronological
  age advances only once per primary world tick.
- Births have a 40-primary-tick parental cooldown and obey the world's population
  capacity, including queued children. A name collision gets a numeric suffix.
- There are at most 64 cultural concepts, 8 annexes, 48 factions, 32 active wars,
  and 16 simultaneous diffusion waves by default. A pair has a ten-tick meme cooldown.
- Maximum-health city grants do not stack through reentry and total capacity is
  capped at 140. Structural anxiety reduction is capped at 40. Trauma can still
  produce acute fear or distress.
- Price multipliers are capped at 1000 and absolute prices at 1,000,000. Attention
  fades with time. This is a fictional attention-driven market, not a real-world
  valuation or calibrated economic forecast.
- If no fair barter is available, the trader can use the existing item-to-coins
  conversion on a cheap holding. This consumes the item and mints its quoted value
  as currency; a cash-holding Lonk can later buy an affordable item without needing
  another barter object. Taxes on purchases are collected from the seller's proceeds.
- A diffusion wave copies an edit delta; it does not discover an optimal gradient
  or guarantee improvement. Harmful edits can spread too. Control creatures may
  still learn normally and experience the same social environment.
- The original base locations form a deterministic ring for proximity and travel;
  each annex attaches to its parent. Diffusion uses this graph, and following a
  crush or seeking an asset moves one edge per action.
- Institutions and romances can dissolve as creatures move or die. Cultural
  canons and the Holy Lexicon remain after their inventors are gone.
- Cultural action preferences come from the inventors' resource needs, wisdom,
  curiosity and loyalty. City laws follow the dominant action preference of the
  locally prevalent canon: trade produces fair-trade protection, thought opens
  schools across faction lines, and social preference produces a sanctuary.
  Fair-trade and sanctuary laws block intimidation trades.
- Dynamic locations live in the runtime config's `generated_locations` and the
  world save. The source `LonkWorld.xc` is not rewritten during play.
- The semantic journal still replays dialogue memory only, not this entire world.

## Lifetimes

`world.lifespan` is honored; without an override the range is 90–180 primary world
ticks. Random aging jumps are removed. `world.random_death_chance` defaults to 0;
setting a finite value in [0,1] explicitly enables per-primary-tick accidents.
Combat and old age can still kill a Lonk, and death messages state the cause.

Loading an older save keeps each living Lonk's age but extends legacy short
lifespans to at least the configured minimum. Dead Lonks are not resurrected.

## Configuration

Optional top-level `civilization` keys in the initial configuration override these
defaults. Saved settings win when a world is loaded.

```json
{
  "civilization": {
    "meme_arousal": 0.65,
    "meme_valence": 0.45,
    "meme_cooldown": 10,
    "max_concepts": 64,
    "annex_population": 4,
    "annex_shared_tokens": 3,
    "max_annexes": 8,
    "romance_ticks": 4,
    "romance_arousal": 0.6,
    "birth_cooldown": 40,
    "settlement_ticks": 5,
    "city_ticks": 10,
    "market_sensitivity": 0.28,
    "max_price_multiplier": 1000,
    "diffusion_rate": 0.25,
    "max_waves": 16
  }
}
```
### Terminal map, colors, and emoji expression

Interactive terminals now keep a compact connected map above a scrolling event
feed during ticks. Every narrated line updates both views, with matching room
numbers and emoji identities. Combat, gifts, romance, speech and growth mark the
active room. Moving Lonks animate along real trails; shared-room gifts and combat
animate between the participants. With TTS on, animation advances with the typed
utterance. Without speech, short animation pauses keep actions visible.

Spoken dialogue and whispers also appear in a cyan speech bubble inside the
speaker's room, with a `▶` marker beside the speaker. The bubble uses only the
characters already typed by the existing narrator, so it never reveals speech
ahead of TTS or queues a second voice. Long utterances wrap and scroll through
three bubble lines; the event feed retains the full text. Bubble space is
reserved for the utterance to keep the room and trails stable while typing.
The bubble clears when narration finishes. With voice off it remains briefly
for reading before the next event.

The focused Lonk's room and inventory appear above the map. Larger worlds page
to the active room automatically; compact room labels/rosters may abbreviate.
`/map` displays the expanded roster, inventories, dropped items and growth details.
`/live off` restores ordinary scrolling narration plus the end-of-tick map;
`/live on` restores the live view. Ctrl+C still pauses automatic mode and leaves
the input prompt available. Help and expanded reports use normal scrolling output.
Unsupported, redirected, or very small terminals retain the scrolling view.

Rooms are arranged in columns with ASCII trails routed around their borders.
The trails follow actual world edges, including new annex links; `x` marks a
crossing rather than a new junction. Each room's Paths list gives exact destinations.
Carrying lines show each Lonk's current inventory; Ground shows dropped items.
The expanded layout fits the terminal width (minimum 40 columns), with a single
column for narrower windows. Its crowded rooms expand rather than hiding names.
Each Lonk has a stable emoji body derived from its saved identity, with its name
beside it. The map includes paths, annex parents, settlement progress, schools,
shrines, and laws. Emoji columns are measured when wrapping map cards.

Interactive terminals use red for combat, pink for romance, green for growth
and recovery, yellow for items and trade, blue for dreams and cults, and cyan
for conversation. Redirected output stays plain; `NO_COLOR` disables colors.
The map is visual; tick narration still speaks the actual events in order.
Player gifts, interactions, speech and society commands update the same live
event feed immediately without advancing a tick. Input resumes after narration
completes; background voice workers never redraw the terminal.

Room positions now constrain physical interactions. Ambient conversation,
teaching, gifts, help and combat select co-located partners. An explicit remote
action walks one graph edge toward its target instead of acting across the map.
Wandering, following and seeking use actual edges; disconnected rooms cannot be
reached by teleporting. Player speech and gifts retain the player's world-wide
access. Vocabulary, society data and saving retain their existing formats.

Lonks can explore the installed Unicode pictograph repertoire and learn emoji
sent through `/say`. Learned joined emoji, skin tones, flags, and keycaps remain
whole and can spread through conversations. This bounded emoji vocabulary is
saved in each Lonk's wordplay state. Emoji expression uses no API or local LLM;
which glyphs render depends on the terminal's font and Unicode support.

