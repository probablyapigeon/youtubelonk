# Local quote library

Restart the game, then `load` your world before importing a library:

```text
/quotes load quote_library/rick_and_morty_starter.txt
/quotes teach Grub
/quotes on 12
```

Use a current Lonk name from `stats`. The included starter contains four example lines; add your chosen quotes to that file or import another file.
No model, API key, network connection, or new Python package is needed.

## Make your own collection

Save UTF-8 text with one complete quote on each line. Blank lines and lines
beginning with `#` are ignored. For a downloaded local repository, point `/quotes
load` at its actual quote data file, rather than a GitHub URL or source-code file.
Paths containing spaces must be quoted:

```text
/quotes load "C:\Users\YourName\Downloads\My Quotes\quotes.txt"
```

JSON accepts an array of strings, an array of objects containing `quote` or
`text`, or an object with a `quotes` array. JSONL accepts one such string/object
per line. Files are limited to 2 MB, 5,000 distinct quotes, and 2,000 characters
per quote. Importing replaces the bank, removes duplicate quotes, and leaves
existing learned Lonk vocabulary intact. A malformed import keeps the old bank.

## How learning works

`/quotes teach NAME` picks one quote for that Lonk to read aloud. The quote appears
in the existing speech bubble and TTS path. Nearby Lonks hear it; distant Lonks
do not receive a global copy. The reader learns vocabulary, emoji, and short
phrase chunks through the same phrase learner used for player speech. Later
dialogue can reuse and combine those chunks with local thoughts and culture.
Importing does not replace the dialogue generator with fixed quote responses.

`/quotes on 12` teaches one random living Lonk one quote every 12 world ticks.
Automatic learning is off until explicitly enabled. It avoids giving a Lonk
the exact same quote twice consecutively when alternatives exist.

```text
/quotes status
/quotes off
/quotes clear
```

Turning off/clearing the library does not erase phrases already learned. The
world save retains the imported bank, automatic-learning setting, cadence, and
individual Lonk memories, so you do not need to re-import after `load`.
