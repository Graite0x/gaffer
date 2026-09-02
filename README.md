<div align="center">

# gaffer

**Plans the work. Runs the fleet. Takes done back.**

[![tests](https://img.shields.io/badge/tests-42%20passing-2ea043)](#tests)
[![deps](https://img.shields.io/badge/runtime%20deps-0-2ea043)](#install)
[![python](https://img.shields.io/badge/python-3.9%2B-3776ab)](#install)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

On a film set the gaffer is the one who calls the shot ready. Nothing is in the can
until they say so — and they can send the whole crew back to reshoot.

That is this tool. It drafts the plan, schedules the fleet, and it is the only thing
here allowed to say a task is finished. Or that it is not, after all.

```
        your one line of intent
                 │
            gaffer plan ──────────► rejected if the scheduler cannot walk it
                 │
            gaffer waves ─────────► T001 · [T002 T003] · T004
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
 git worktree            git worktree          one per task, no shared files
     │                       │
   gate ✓                  gate ✗              a command with an exit code
     │                       │
   merged              branch dropped          HEAD restored, dependents blocked
                             │
                    gaffer unfinish ─────────► and done can still be taken back
```

---

## Sixty seconds

```sh
git clone https://github.com/Graite0x/gaffer && cd gaffer
./gaffer plan "add rate limiting to the API" --scaffold --gate "pytest -q"
./gaffer waves
```

```
setup:
      T001  Setup: scaffold for add rate limiting to the API
foundational:
      T002  Foundational: the piece every later task needs -> T001
work:
  [P] T003  Work A: independent slice, own files -> T002
  [P] T004  Work B: independent slice, own files -> T002
polish:
      T005  Polish: integrate and prove the whole thing -> T003 T004

5 nodes, 4 waves
  ~ no command, nothing to run: T001, T002, T003, T004, T005
```

That warning is the scaffold telling the truth: it is a shape, not your work.
Write commands into `graph.md`, or hand one to every node at once — each gets
`$GAFFER_NODE` in its environment:

```sh
./gaffer run --cmd 'claude -p "$GAFFER_NODE" && git add -A && git commit -m "$GAFFER_NODE"'
```

```
  ok  T001  merged
  ok  T002  merged
  ok  T003  merged
  ok  T004  merged
  ok  T005  merged
green: 5/5
```

Now the part that matters:

```sh
./gaffer unfinish T005 --reason "the gate was assert True"
./gaffer status
```

```
took back T005: the gate was assert True
done    T001, T002, T003, T004
failed  T005
next    T005
```

And when a gate is actually red, nothing gets merged and the dependents never start:

```
  ok    T001  merged
  ok    T002  merged
  FAIL  T003  gate failed: test -f NEVER_EXISTS.txt
  FAIL  T004  blocked by T003
blocked: 2/4
```

The scheduler did not ask a model whether that was fine.

---

## What this is

The ten-repo map from *[A Graph of Loops](https://x.com/Granite0x/status/2080665298609328201)*
had two layers and no wiring between them. Bernstein schedules a fleet. Waku is a
loop you can read. Nobody put both in one binary — so this is that binary.

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
`gaffer doctor` tells you which slots you actually have.

---

## Planning

The DAG used to be yours to write. `gaffer plan` writes the first draft — and
then refuses it if the scheduler cannot walk it.

```sh
gaffer plan "add rate limiting" --gate "pytest -q"    # prints a prompt for your agent
gaffer plan --from answer.json --out graph.md         # reads the answer back
gaffer plan "add rate limiting" --scaffold            # no model at all
```

Three doors, one contract:

| door | what happens | when |
|---|---|---|
| `plan "<idea>"` | prints a prompt asking for JSON — paste it into Claude Code, Codex, anything | you want the model's judgement |
| `plan --from <file>` | parses the answer, reviews it, renumbers T001.. in wave order, writes the graph | the model answered |
| `plan --scaffold` | lays down the phase shape with no model in the loop | you already know the shape |

It asks for JSON rather than prose because JSON is cheaper to check. Nothing
reaches disk until the plan survives review:

```
rejected:
  ! cycle: A -> B -> A
  ! T004 is work but does not wait for foundational
  ! T003 is marked [P] but depends on [P] T002
```

Missing commands and gates are **warnings**, not errors — a scaffold is
unfinished on purpose. A cycle is an error, because `waves()` cannot walk it.

**The model proposes. The code accepts.** Same contract as the gate: a plan a
model likes is not a plan until the scheduler agrees it can run.

`gaffer plan` calls no API. It prints a prompt for the agent you already pay for.

---

## The graph

A node is a checklist line or a JSON object. `[P]` nodes ready at the same time
share a wave; everything else is serial. Cycles are a hard error.

```
- [ ] [T001] Scaffold
- [P] [T002] Fan-out A -> T001
- [P] [T003] Fan-out B -> T001
- [ ] [T004] Merge point -> T002 T003
```

Because that is spec-kit's line format, **a `tasks.md` written by spec-kit runs
here with no converter.**

## The loop

Each node: own git worktree → command (or in-process loop) → code gate →
dry-run merge. Conflict or a red gate and you get **Merge aborted due to
conflicts**, HEAD restored, node marked failed, dependents blocked.

## The one test

```sh
gaffer run examples/graph.json --repo .
gaffer unfinish T004 --reason "gate was assert True"
gaffer status
```

If `T004` is still in `done`, the system cannot take done back, and you do not
have a system. Beads, if installed, gets the same reopen.

---

## Install

```sh
./gaffer init      # graph.md + .gaffer/state.json
./gaffer doctor    # which of G1–L6 you actually have
```

Or `pip install -e .` on Python 3.9+ with a current pip, then `gaffer`.

## Commands

```sh
gaffer init                   # graph.md + .gaffer/state.json
gaffer plan "<what you want>" # draft a graph, three ways
gaffer waves                  # print the schedule — no model, no spawn
gaffer run --cmd '…'          # walk it; merge only if the gate is green
gaffer unfinish T002          # take done back
gaffer status                 # done, failed, next
gaffer doctor                 # slot inventory
```

---

## What we took, what we did not

| Slot | Upstream | Here |
|---|---|---|
| G1 | [bernstein](https://github.com/sipyourdrink-ltd/bernstein) — 1,765 Python files, task server, `.sdd/` | ~80 lines: DAG, cycle detect, `[P]` waves |
| G2 | [agent-worktree](https://github.com/nekocode/agent-worktree) | raw `git worktree` + dry-run merge; uses `wt` if on PATH |
| L1 | [beads](https://github.com/gastownhall/beads) | shells out to `bd`; RunState works without it |
| L2 | [waku-agent](https://github.com/ShenSeanChen/waku-agent) `waku/loop/agent.py` | same trick, no Anthropic client, tool errors are not swallowed |
| L5 | [claude-review-loop](https://github.com/hamelsmu/claude-review-loop) | a file on disk that only code may write; `unfinish` |
| plan | [spec-kit](https://github.com/github/spec-kit) — 133k★, six slash commands, its own `.specify/` tree | the phase order and the task line, ~180 lines; spec-kit output runs unconverted |
| plan | [supervisor](https://github.com/ObedienceAdara/supervisor) — calls Anthropic/Groq itself | prompt out, JSON in, no SDK and no API key |

Nothing above is vendored. `NOTICE` has the attributions.

Closest existing composers — and why they are not this:

- [The Claude Protocol](https://github.com/AvivK5498/The-Claude-Protocol) — 13 Claude Code hooks + beads + worktrees. Enforcement plugin, not a scheduler you can run without Claude.
- [reeds](https://github.com/rikdc/reeds) — beads + Ralph stop-hook. One loop, no DAG.
- [insane-research](https://github.com/fivetaku/insane-research) — the shape, for research, as a plugin. Steal `validate_ledger.py`; do not skip the gate.
- [beads-superpowers](https://github.com/DollarDill/beads-superpowers) — L1+L4 only.

Search GitHub for the ten names together and you get zero repos. That is the hole.

## Traps we kept honest

- `gaffer plan` drafts the DAG; it does not know your codebase. Read the plan before you run it.
- Isolation is not a scheduler. `gaffer waves` decides how many nodes spawn.
- Serena verifies nothing. Superpowers is persuasion. The gate is the syscall.
- If `doctor` says `L1 !` your `.beads/` is on iCloud or Dropbox. Move it.
- Replay/eval tools can hit a real database if you point them at a production handler.

## Tests

```sh
pip install -e ".[dev]" && pytest -q     # 42 tests, ~1s
```

MIT.
