# Semantic interpretation and its evidence

The dialogue pipeline now has two separate representations:

1. The record preserves the exact input, speaker, agent identity, tick and reply.
2. The interpretation extracts supported subject/verb/object relations, tense,
   negation and modality. Unrecognized clauses remain explicitly unparsed.

For example, `I found a blue rock. I do not like moss.` produces two distinct
assertions. Both enter conversational memory; later questions can retrieve each.
`I found a blue rock. I lost it.` resolves the second clause's referent to the rock.
A chant can remain unparsed while the separate phrase learner remembers its wording.

This is a symbolic projection, not general English understanding or necessarily
compression into fewer bytes. It does not assign an arbitrary scalar and call that
the meaning. Emotional interpretation and response selection remain separate.

## Inspect and verify

Restart the simulator to load the implementation. Incoming and spontaneous dialogue
turns append to `lonk_semantic_events.jsonl` in the current directory. The optional
top-level configuration key `semantic_trace_path` changes that path.

Use `/listen <name>` to see the last interpretation, its unparsed clause count and
its trace sequence number. The existing memories and commands remain available.

Run `python lonk_semantics.py lonk_semantic_events.jsonl` to verify the hash chain
and reconstruct the recorded dialogue-memory contexts.

Each record contains changed memory fields. A baseline is included for a new
context or a context restored from an earlier save; restores remain explicit in
the appended history. Saved agent IDs distinguish creatures with reused names.

## Boundaries

- This replays the dialogue-memory projection, not all world state, randomness,
  neural-network updates, or exact output timing.
- The log preserves original language even when the interpretation loses meaning.
- A matching hash chain detects edits without recomputed hashes. It is not a
  signature, externally anchored proof, or protection against rewriting the entire
  chain or truncating its tail.
- One simulator process owns a trace file. Use different configured paths for
  concurrent worlds.
- The trace contains verbatim conversation text. It stays on this computer.
- No LLM, remote service, API key, or new package is required.
