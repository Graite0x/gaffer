# goloops

**Graph on top. Loop underneath. A system that can take done back.**

This is the wiring layer the ten-repo map never shipped. Bernstein schedules a fleet. Waku is a loop you can read. Nobody put both in one binary — so this is that binary, and nothing else.

```
THE GRAPH                         THE LOOP
coordinate the fleet              make one node trustworthy

G1 ● Orchestrate                  L1 ○ Memory     (bd, if you have it)
G2 ● Isolation                    L2 ● Loop core  (this repo)
G3 ○ Roles                        L3 ○ Context    (serena)
G4 ○ Already-ships                L4 ○ Skills     (superpowers)
                                  L5 ● Gate       (this repo)
                                  L6 ○ Proof      (workshop)
```

● is this repo. ○ is an optional CLI or plugin. Do not install all 203 roles.

## Install

```sh
./goloops init
./goloops doctor
```

Or `pip install -e .` on Python 3.9+ with a current pip, then `goloops`. Git required. Zero runtime dependencies.

## The instrument

```sh
goloops init                 # graph.md + .goloops/state.json
goloops waves                # print the schedule — no model, no spawn
goloops run --cmd '…'        # walk it; merge only if the gate is green
goloops unfinish T002        # take done back
goloops status
goloops doctor               # which of G1–L6 you actually have
```

A node is a checklist item or a JSON object. `[P]` nodes that are ready at the same time share a wave. Everything else is serial. Cycles are a hard error.

```
- [ ] [T001] Scaffold
- [P] [T002] Fan-out A -> T001
- [P] [T003] Fan-out B -> T001
- [ ] [T004] Merge point -> T002 T003
```

Each node: own git worktree → command (or in-process loop) → code gate → dry-run merge. Conflict or a red gate: **Merge aborted due to conflicts**, HEAD restored, node marked failed. The scheduler never asks a model whether that was fine.

`goloops unfinish T002` is the one test. Beads, if installed, gets the same reopen.

## What we took, what we did not

| Slot | Upstream | Here |
|---|---|---|
| G1 | [bernstein](https://github.com/sipyourdrink-ltd/bernstein) — 1,765 Python files, task server, `.sdd/` | ~80 lines: DAG, cycle detect, `[P]` waves |
| G2 | [agent-worktree](https://github.com/nekocode/agent-worktree) | raw `git worktree` + dry-run merge; uses `wt` if on PATH |
| L1 | [beads](https://github.com/gastownhall/beads) | shells out to `bd`; RunState works without it |
| L2 | [waku-agent](https://github.com/ShenSeanChen/waku-agent) `waku/loop/agent.py` | same trick, no Anthropic client, tool errors are not swallowed |
| L5 | [claude-review-loop](https://github.com/hamelsmu/claude-review-loop) | a file on disk that only code may write; `unfinish` |

We did not vendor bernstein. We did not fork The Claude Protocol. We did not wrap all ten installers. `NOTICE` has the attributions.

Closest existing composers — and why they are not this:

- [The Claude Protocol](https://github.com/AvivK5498/The-Claude-Protocol) — 13 Claude Code hooks + beads + worktrees. Enforcement plugin, not a scheduler you can run without Claude.
- [reeds](https://github.com/rikdc/reeds) — beads + Ralph stop-hook. One loop, no DAG.
- [insane-research](https://github.com/fivetaku/insane-research) — the shape, for research, as a plugin. Steal `validate_ledger.py`; do not skip the gate.
- [beads-superpowers](https://github.com/DollarDill/beads-superpowers) — L1+L4 only.

Search on GitHub for the ten names together returns zero repos. That is the hole.

## Traps we kept honest

- The DAG is hand-authored. This does not infer your graph.
- Isolation is not a scheduler. `goloops waves` decides how many nodes spawn.
- Serena verifies nothing. Superpowers is persuasion. The gate is the syscall.
- If `doctor` says `L1 !` your `.beads/` is on iCloud or Dropbox. Move it.
- Replay/eval tools can hit a real database if you point them at a production handler.

## One test

```sh
goloops run examples/graph.json --repo .
goloops unfinish T004 --reason "gate was assert True"
goloops status
```

If `T004` is still in `done`, the system cannot take done back, and you do not have a system.
