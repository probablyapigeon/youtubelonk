# YouTube comments in Lonk World

The bridge reads YouTube live chat and feeds viewer messages into the existing
Lonk language, gifts, rumors, map bubbles and TTS. It does not use an LLM and
does not post replies to YouTube. The network reader only queues messages;
the simulation thread applies them between Lonk actions.

## One-time setup

Connect your current broadcast using its watch, Share, or Studio URL. The bridge
remembers the stream locally for future reconnects.

1. Create/select a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **YouTube Data API v3** in the API Library.
3. In **APIs & Services → Credentials**, create an API key for that project.
4. Restart Lonk World, then run:

```text
load
/youtube setup
```

Enter the API key at the hidden prompt. Then:

```text
/youtube connect YOUR_STREAM_URL
/youtube status
/tts on
/auto on
```

The key is entered privately instead of echoing into the stream's terminal.
This public-chat reader uses a Data API key, not a YouTube password or stream
ingest key. Public/unlisted live video chat must be available; private broadcasts
require a different authorization flow and are not supported by this bridge.
Google's setup is documented in the [authorization guide](https://developers.google.com/youtube/v3/guides/authentication).

## Reconnect next time

```text
/youtube reconnect
```

No need to enter the key again. For a new broadcast:

```text
/youtube connect https://www.youtube.com/watch?v=NEW_VIDEO_ID
```

Watch, `/live/`, short `youtu.be`, Studio links, and bare video IDs are accepted.
The new stream replaces the remembered one. Temporary network failures retry
automatically with backoff; quota, credential and ended-chat errors stop the
reader and appear in `/youtube status` instead of retrying indefinitely.

```text
/youtube status
/youtube disconnect
```

Pause `/auto` with Ctrl+C to type these commands. Disconnect clears pending
comments. Quitting stops the reader. Restarting the game does not automatically
connect; use `/youtube reconnect` when you want chat intake again.

## Viewer commands

Use current Lonk names from the map or `stats`:

```text
!say Grub hello moss friend
!say Glump fuck 🧑🏽‍🚀
!gift Grub moss
!gossip Glump found a portal
```

The default mode accepts these three commands only. `!say` maintains separate
dialogue context by viewer channel ID and teaches words, sayings, and emoji
through the same machinery as player speech. `!gift` supplies the named Lonk;
`!gossip` tells one living Lonk the viewer's rumor. The recipient hears it,
learns its words/phrase chunks and can pass that rumor to nearby Lonks through
later gossip; its contents are attributed hearsay rather than proven facts.
Gift delivery prints the item/emotion received, and rumor delivery prints who
heard it. Viewers cannot run admin,
save/load, shell, file-import, tuning or connection commands.

To also let ordinary comments reach random living Lonks:

```text
/youtube mode all
```

To return to commands only:

```text
/youtube mode commands
```

Chat applies on simulation ticks. While manually paused, apply one queued
message with `/youtube pump` without advancing a tick. The terminal input prompt
remains yours: the background reader never prints over it or operates the UI.

## Pacing and storage

The first fetched batch is skipped as chat history. Message IDs are deduplicated;
old messages are ignored, including after reconnecting. The queue holds at most
32 messages, favoring recent comments when full. Messages expire after 60
seconds, and each viewer has a 10-second intake cooldown. Comments are not
limited to a fixed count per tick. There are at least two seconds
between applications, and messages can enter after completed narration lines
as well as between Lonk actions. A long spoken tick therefore does not strand
new gifts or rumors until they expire. Cooldowns use comment publication times,
so two properly spaced comments fetched in one batch remain eligible.
Text is limited to 400 characters.

When messages are skipped, `/youtube status` breaks the counts down into
cooldown, expired, queue overflow, and missing target, rather than only showing
a combined dropped count. Reconnect skips history: send new test comments
after status reports connected.

This uses the official [liveChatMessages.list](https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list)
endpoint, never polling faster than the server's refresh interval or 15 seconds.
Requests consume the Google project's YouTube API quota. Responses are displayed
only inside Lonk World; no YouTube message-insertion endpoint is used.

On Windows, local settings live in:

```text
%LOCALAPPDATA%\LonkWorld\youtube.json
%LOCALAPPDATA%\LonkWorld\youtube_credentials.json
```

The first file holds the stream ID and input mode; the second holds the API key.
Neither is included in `lonk_world.json`. Viewer dialogue, memories, learned
words and received items save as ordinary Lonk state. An optional process
environment variable `YOUTUBE_API_KEY` takes precedence over the saved key.

## Status meanings

- **connecting**: resolving the stream and fetching the initial history batch.
- **connected**: polling new chat. It may still be waiting for commands or a tick.
- **retrying / networkInterrupted**: transient failure; automatic retry pending.
- **retrying / waitingForLiveChat**: video exists but no active chat is available yet.
- **error / keyInvalid or accessNotConfigured**: check the key and enabled API.
- **error / API_KEY_SERVICE_BLOCKED**: the saved key's API restrictions block
  YouTube. In the key's owning project, open Credentials, select that key, allow
  **YouTube Data API v3** under API restrictions, and save. This is different
  from just enabling the API for the project. If editing a different/new key,
  enter that edited key using `/youtube setup` before reconnecting.
- **error / SERVICE_DISABLED**: enable YouTube Data API v3 in the key's project.
- **error / quotaExceeded**: the project's API quota is exhausted.
- **ended or liveChatEnded**: start another broadcast and connect its new URL.

Connection notices appear on the main thread during ticks, or inspect them
immediately with `/youtube status`. The key and raw HTTP error URLs are never
printed in those notices.
