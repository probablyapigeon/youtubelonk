# YouTubeLonk 

A terminal civilization simulator full of little Lonks who learn words, trade
items, form relationships, invent cultural phrases, and build increasingly
weird societies. YouTube livestream viewers can talk to them, give gifts, and
seed rumors through live chat.

Dialogue uses an offline procedural grammar, learned vocabulary, and phrase
recombination. YouTube chat is an optional, read-only network integration. Leave
`WP_API_KEY` unset to keep the existing weight programmer in its default
analytical mode; the legacy optional LLM programmer is not needed to play.

## Run it on Windows

Tested with Python 3.12. Open PowerShell:

```powershell
git clone https://github.com/probablyapigeon/youtubelonk.git
cd youtubelonk
python -m pip install -r requirements.txt
$env:PYTHONIOENCODING="utf-8"
python dynamiclonk-py-v13-lonks-finally-have-ears-say-command-fixed.py --config LonkWorld.xc
```

Press Enter for one tick. Useful terminal commands:

```text
help
/tts on
/auto on
/map
/live off
stats
save
load
quit
```

Ctrl+C pauses automatic mode and returns to the command prompt. In manual mode,
Ctrl+C saves and exits. `quit` also saves. A new session starts a fresh world;
use `load` to continue your previous `lonk_world.json`.

The live map shows connected rooms, emoji bodies, inventories, cities and annexes.
Dialogue types into room speech bubbles with TTS pacing. The expanded `/map`
shows full rosters and item details. A compatible terminal such as Windows Terminal
with emoji-capable fonts gives the clearest view. Redirected/unsupported terminals
use ordinary scrolling output. TTS uses Windows SAPI; other platforms use the
pyttsx3 fallback and may require an installed speech backend.

## Talk to your Lonks

Use current names from `stats`:

```text
/say Grub hello moss friend
/gift Grub moss
/gossip Grub stole the moon
/observe Grub
/listen Grub
```

Names, characters, emotional states, items and locations change as the world runs.
The small grammar has limits; learned phrases can be strange or repetitive.

## Connect YouTube live chat

Enable YouTube Data API v3 in a Google Cloud project and create an API key once.
The [YouTube setup guide](YOUTUBE_LIVE_CHAT.md) walks through this process.
In the Lonk terminal:

```text
/youtube setup
/youtube connect YOUR_STREAM_URL
/youtube status
/tts on
/auto on
```

Replace `YOUR_STREAM_URL` with your current broadcast's Share/watch/Studio link.
The setup command accepts the API key through a hidden prompt. The bridge stores
connection settings and credentials outside the world save under
`%LOCALAPPDATA%\LonkWorld` on Windows. This repository contains no saved credentials.

After restarting, `/youtube reconnect` uses the remembered broadcast and key.
A new broadcast has a new URL: use `/youtube connect` with that new link.

Viewers type these in **YouTube chat**, using current living Lonk names:

```text
!say Grub hello you little freak
!gift Grub moss
!gossip Glump stole the moon
```

`/youtube mode all` also lets ordinary comments reach random Lonks;
`/youtube mode commands` restores the default command-only mode. `/youtube pump`
applies one queued comment while manually paused. `/youtube disconnect` stops intake.

Comments enter between completed narration lines on the main simulation thread.
The reader uses a bounded queue, per-viewer cooldowns, stale-message expiry, and
message deduplication. It skips initial chat history, retries temporary failures,
and does not post replies to YouTube. Gift receipts and rumor acknowledgements
appear in the feed. `/youtube status` explains skipped messages and API errors.

## Teach a quote library

```text
/quotes load quote_library/rick_and_morty_starter.txt
/quotes teach Grub
/quotes on 12
/quotes off
```

The small starter can be replaced or extended with your chosen quotes. Text files
use one quote per line; JSON and JSONL are also accepted. Readers learn words and
short phrase chunks that can spread and recombine, while nearby Lonks hear the
reading. Automatic teaching is opt-in. See [quote library instructions](quote_library/README.md).

## Civilization and learning

- Emotions respond to treatment, learning, gifts and trauma.
- Local conversation, trading and combat follow room positions and real paths.
- Crushes, jealousy, offspring, cults, cultural concepts, schools and growing cities
  interact with the existing action and learning systems.
- The analytical weight-space programmer edits a chosen Lonk; resonant diffusion
  can propagate edits while the control twin remains excluded.
- Semantic traces retain text and symbolic interpretations. Dialogue-memory replay
  is distinct from full-world deterministic replay.

Read [civilization systems](CIVILIZATION_SYSTEMS.md),
[semantic compression](SEMANTIC_COMPRESSION.md), and
[YouTube connection details](YOUTUBE_LIVE_CHAT.md) for mechanisms and limits.

## Run the regression checks

From this repository's root:

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m unittest test_lonk_youtube test_lonk_quotes test_lonk_live test_lonk_map test_lonk_visuals test_lonk_lifecycle test_lonk_society test_lonk_cooperation test_lonk_semantics test_lonk_dialogue test_lonk_emotions test_tts_regression -q
```

These tests use fake YouTube responses and speech engines; they do not require a
live broadcast or credentials. Personal saves, traces, credentials and environment
files are excluded from Git. Back up your world save before experimenting.

Developed from [probablyapigeon/wetlonk](https://github.com/probablyapigeon/wetlonk).
