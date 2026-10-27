# flushNcontinue

**Claude Code remembers your project between sessions.**

Each session starts where the last one stopped, saves its progress as it works, and
hands off cleanly at the end. The memory lives in plain files inside the project, so
it is in git, reviewable, and shared with the team.

---

## What you get

- **A session that resumes.** On start, Claude reads the project's handoff file
  (`state/BRIEF.md`), tells you where things stopped, and asks "continue?".
- **Three commands.**
  - `/checkpoint` saves the current thread in seconds.
  - `/flush` does the full end-of-session update.
  - `/kbinit` gives a new project its own memory.

---

## Before you start

You need all four:

- [ ] macOS or Linux
- [ ] `git` and `python3` (check: `git --version` and `python3 --version`)
- [ ] Claude Code installed and signed in (check: `claude --version`)
- [ ] Access to this repo on GitHub (check: `gh auth status`; if it fails, run `gh auth login`)

---

## Install: 4 steps, about 5 minutes

### Step 1: Clone

```bash
mkdir -p ~/apps
gh repo clone rdhillbb/flushNcontinue ~/apps/flushNcontinue
```

✅ You should see: the folder `~/apps/flushNcontinue` exists.

### Step 2: Preview (changes nothing)

```bash
bash ~/apps/flushNcontinue/install.sh --dry-run
```

✅ You should see: a list of `do ...` lines, ending with `dry run: nothing was written.`

❌ If you see `STOP`: do what that line says, then repeat Step 2.

### Step 3: Install

```bash
bash ~/apps/flushNcontinue/install.sh
```

✅ You should see: `installed.` at the end.

Nothing is deleted. Anything the installer replaces is kept next to the original as
`*.bak-flushNcontinue-<date>`.

### Step 4: Check

```bash
bash ~/apps/flushNcontinue/install.sh --check
```

✅ You should see: `check: clean`.

---

## Finish setup: 2 minutes

**1. Add your name and time zone.** Open `~/.claude/CLAUDE.md` and fill in the two
`<fill in>` lines.

(If you already had this file, the installer did not touch it. You can copy what you want
from `~/apps/flushNcontinue/templates/personal-CLAUDE.md`.)

**2. Restart Claude Code and test it in a project**

```bash
cd ~/apps/<your-project>
claude
```

✅ You should see, before anything else:
- `=== SESSION BRIEF ===`, followed by the project's handoff note
- a time banner
- a `SESSION HEALTH` line

Then Claude says where the last session stopped and asks
*"No issues? Then I continue with …"*.

If the project has no `state/BRIEF.md` yet, you won't see the BRIEF. That is normal.
See [New project](#new-project).

---

## Daily use

| When | You do | What happens |
|---|---|---|
| **Start a session** | Nothing. Answer Claude's "continue?" | The hook loads BRIEF automatically |
| **After each decision or finished step** | `/checkpoint` | The thread is saved into BRIEF (about 20 s). A crash loses nothing |
| **End of session, or context at 62%** | `/flush`, then start a new session | Knowledge files updated and committed locally |

**Three rules:**
1. **Never let context go past 70%.** Flush at 62% and start fresh.
2. **`/flush` commits, but never pushes.** You push when your normal git process says so.
3. **Never put a secret in these files.** Write the key's name plus "fetch live".

---

## Updating

```bash
cd ~/apps/flushNcontinue
git pull
bash install.sh --check
```

The skills are links into this folder, so `git pull` updates them right away. Re-run
`bash install.sh` only if `--check` reports a problem.

---

## New project

To give a project that has **no** knowledge base its own memory, open Claude in that
project and run:

```
/kbinit
```

For a project that **already has** one (it has `KNOWLEDGE-MAP.md`), never run `kbinit`.
To refresh its tooling instead:

```bash
bash ~/bin/kb_upgrade.sh --dry-run .
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| No `SESSION BRIEF` when Claude starts | Start `claude` **inside** the project folder. Run `bash ~/apps/flushNcontinue/install.sh --check`. Restart Claude Code. |
| `/checkpoint` or `/flush` is unknown | Run `ls -l ~/.claude/skills/`. Each skill should point into `~/apps/factorymaterial/claude/skills/`. If not, re-run `install.sh`. |
| `STOP … is a real folder, not this clone` | You already have a `~/apps/factorymaterial` folder. Rename it (for example to `factorymaterial.old`), then run Step 2 again. |
| `STOP … is not valid JSON` | `~/.claude/settings.json` has a typo. Fix it, then run Step 3 again. |

---

## Undo

1. Remove the links listed in [What gets installed](#what-gets-installed).
2. Restore `~/.claude/settings.json` from its `settings.json.bak-flushNcontinue-<date>` copy.
3. Restart Claude Code.

---

## Reference

### What gets installed

Everything is under your home folder, and nothing outside it is touched.

| Location | What |
|---|---|
| `~/apps/factorymaterial` | A link to this clone. The skills refer to this path. |
| `~/.claude/skills/` | Links: `checkpoint`, `flush`, `kbinit` |
| `~/.claude/settings.json` | Two hooks added; your other settings are kept. **SessionStart** loads BRIEF; **PreCompact** saves the thread if a session compacts. |
| `~/bin/` | Links: `session_time.sh`, `kb_tools.py`, `kb_upgrade.sh`, `kb_handoff.sh` |
| `~/.claude/CLAUDE.md` | Your personal rules. Created only if you had none. |

### The knowledge files inside a project

| File | Holds |
|---|---|
| `state/BRIEF.md` | Where the last session stopped: task, next step, open questions |
| `state/NOW.md` | What is true right now |
| `state/FINDINGS.md` | Open problems, one line each (`F-NN`) |
| `state/CONTRADICTIONS.md` | Docs known to be out of date (`C-NN`) |
| `docs/tribal/<year>-Q<n>.md` | Dated history. Append-only, never edited |
| Pitfalls file | Traps that cost time before (`P-NN`) |
| `KNOWLEDGE-MAP.md` | Where each fact lives, and which file wins |

**When files disagree:** the live system wins, then NOW, then CONTRADICTIONS, then FINDINGS.

**Branches:** these files are in git, so every branch has its own copy. Merge `main` into
your branch often. When they conflict, keep **both** sides' entries.

### What is in this repo

| Folder | Contents |
|---|---|
| `install.sh` | The installer (`--dry-run`, `--check`) |
| `hooks/` | `session-start.sh`, `pre-compact.sh` |
| `claude/skills/` | The three skills: `checkpoint`, `flush`, `kbinit` |
| `claude/kb/` | Templates `kbinit` uses to create a new knowledge base |
| `scripts/` | `kb_tools.py` (the engine behind flush), `kb_upgrade.sh`, `kb_lint.sh`, tests |
| `bin/` | `session_time.sh` |
| `templates/` | `personal-CLAUDE.md` |
