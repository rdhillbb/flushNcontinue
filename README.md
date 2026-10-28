# flushNcontinue

**Claude Code remembers your project between sessions.**

Each session starts where the last one stopped, saves its progress as it works, and
hands off cleanly at the end. The memory lives in plain files inside the project, so
it is in git, reviewable, and shared with the team.

---

## What you get

- **A session that resumes.** On start, Claude reads the project's handoff file
  (`state/BRIEF.md`), tells you where things stopped, and asks "continue?".
- **The date and time first.** Every session starts with a time banner
  (Cambodia, US Eastern, UTC), so Claude never guesses the day.
- **Three commands.**
  - `/checkpoint` saves the current thread in seconds.
  - `/flush` does the full end-of-session update.
  - `/kbinit` gives a new project its own memory.

The installer works on **one project at a time**. It copies the files into that
project's `.claude/` folder. It does not touch your home folder; the one home-folder file,
`~/bin/session_time.sh`, you copy by hand once per computer.

> **On Windows?** Skip to [Windows](#windows). It is a complete step-by-step guide from a
> new PC, and you do not need the Mac/Linux steps below.

---

## Before you start (Mac and Linux)

You need all of these:

- [ ] `git` (check: `git --version`)
- [ ] Python 3.8 or newer, runnable as `python3` (check: `python3 --version`)
- [ ] Claude Code installed and signed in (check: `claude --version`)
- [ ] Access to this repo on GitHub (check: `gh auth status`; if it fails, run `gh auth login`)


---

## Install on Mac or Linux: 4 steps, about 5 minutes

In the commands below, replace `~/code/myproject` with your project's folder.

### Step 1: Clone

```bash
mkdir -p ~/apps
gh repo clone rdhillbb/flushNcontinue ~/apps/flushNcontinue
```

✅ You should see: the folder `~/apps/flushNcontinue` exists.

### Step 2: Preview (changes nothing)

```bash
bash ~/apps/flushNcontinue/install.sh ~/code/myproject --dry-run
```

✅ You should see: a list of `ok ...` and `do ...` lines, ending with
`dry run: nothing was written.`

❌ If you see `STOP`: do what that line says, then repeat Step 2.

### Step 3: Install

```bash
bash ~/apps/flushNcontinue/install.sh ~/code/myproject
```

✅ You should see: `installed into .../myproject/.claude` at the end.

Nothing is deleted. Anything the installer replaces is moved to
`.claude/backups/flushNcontinue-<date>/` inside the project.

### Step 4: Check

```bash
bash ~/apps/flushNcontinue/install.sh ~/code/myproject --check
```

✅ You should see: `check: clean`.

---

## Finish setup: 3 minutes

**1. Your personal rules (once per computer).** If you do not have `~/.claude/CLAUDE.md`
yet, copy the template, then fill in the two `<fill in>` lines (your name and time zone):

```bash
mkdir -p ~/.claude
cp -n ~/apps/flushNcontinue/templates/personal-CLAUDE.md ~/.claude/CLAUDE.md
```

If you already have that file, `cp -n` leaves it alone. Copy what you want from the
template by hand.

**2. The time script in `~/bin` (required, once per computer).** Your rules and skills
run `~/bin/session_time.sh` at the start of every session. Copy it there:

```bash
mkdir -p ~/bin
cp ~/apps/flushNcontinue/claude/hooks/session_time.sh ~/bin/session_time.sh
chmod +x ~/bin/session_time.sh
bash ~/bin/session_time.sh
```

✅ You see a **Session Time Reference** box with Cambodia, US Eastern and UTC times.

**3. Restart Claude Code in the project**

```bash
cd ~/code/myproject
claude
```

✅ You should see, before anything else:
- a **Session Time Reference** banner (Cambodia, US Eastern, UTC)
- `=== SESSION BRIEF ===` with the project's handoff note (only once the project has a
  knowledge base; see [New project](#new-project))
- a `SESSION HEALTH` line (also only once the knowledge base exists)

Then Claude says where the last session stopped and asks
*"No issues? Then I continue with …"*.

**4. Share with the team.** Commit these from the project (not `.claude/backups`):

```bash
git add .claude/skills .claude/hooks .claude/settings.json
git commit -m "Add flushNcontinue session memory"
```

Teammates who pull the project get everything. They only need Step 1 of
[Finish setup](#finish-setup-3-minutes).

---

## Daily use

| When | You do | What happens |
|---|---|---|
| **Start a session** | Nothing. Answer Claude's "continue?" | The hook prints the time and loads BRIEF |
| **After each decision or finished step** | `/checkpoint` | The thread is saved into BRIEF (about 20 s). A crash loses nothing |
| **End of session, or context at 62%** | `/flush`, then start a new session | Knowledge files updated and committed locally |

**Claude cannot see its own context %.** You read it in the Claude Code status bar and
say "flush". Nothing flushes automatically.

**Three rules:**
1. **Never let context go past 70%.** Flush at 62% and start fresh.
2. **`/flush` commits, but never pushes.** You push when your normal git process says so.
3. **Never put a secret in these files.** Write the key's name plus "fetch live".

---

## Updating

The files are **copies**, so a `git pull` alone does not change your projects. Pull,
then re-run the installer in each project:

```bash
cd ~/apps/flushNcontinue && git pull
bash ~/apps/flushNcontinue/install.sh ~/code/myproject
bash ~/apps/flushNcontinue/install.sh ~/code/myproject --check
```

Then commit the changed `.claude/` files so the team gets them too.

---

## New project

To give a project that has **no** knowledge base its own memory, open Claude in that
project and run:

```
/kbinit
```

For a project that **already has** one (it has `KNOWLEDGE-MAP.md`), never run `kbinit`.
To refresh its tooling instead, run from the project folder:

```bash
bash .claude/skills/kbinit/tools/kb_upgrade.sh --dry-run .
```

---

## Windows

> **Not tested on Windows yet.** The steps below follow the official Claude Code Windows
> docs and were checked on a Mac. If a step does not show the ✅ result, stop, copy the
> exact error text, and send it to the repo owner.

Do the parts in order: **A** once per computer, **B** once per project, **C** only if
**B** fails.

### Two windows you will use

| Window | How to open it | Its prompt looks like | Used for |
|---|---|---|---|
| **PowerShell** | Start menu → type `PowerShell` → open **Windows PowerShell** | `PS C:\Users\Paul>` | Only Part A, step 4 (installing Claude Code) |
| **Git Bash** | Start menu → type `Git Bash` → open it | `Paul@PC MINGW64 ~` then `$` | **Everything else** |

**Paths look different in Git Bash.** `C:\Users\Paul\code\myproject` is typed as
`/c/Users/Paul/code/myproject`. `~` means `C:\Users\Paul`.

**Copy and paste in Git Bash:** paste with **right-click → Paste** or **Shift+Insert**
(Ctrl+V may not work).

### Part A: Set up the computer (once)

**A1. Install Git for Windows (required).**
1. Download from https://git-scm.com/downloads/win and run the installer.
2. Click **Next** on every screen; the defaults are fine.
3. Open **Git Bash** and type:
   ```bash
   git --version
   ```
   ✅ You see `git version 2.x.x.windows.x`.

Why it is required: the session hooks are bash scripts. Without Git Bash, Claude Code
runs hooks in PowerShell and they fail.

**A2. Install Python 3.**
1. Open the **Microsoft Store**, search **Python 3.12**, click **Get** (publisher:
   Python Software Foundation).
2. **Close Git Bash and open it again**, then type:
   ```bash
   python3 --version
   ```
   ✅ You see `Python 3.12.x`.

   ❌ It opens the Store, or says `command not found`: the install did not finish. Finish
   it, then close and reopen Git Bash.

**A3. Sign in to GitHub (needed to download this repo).**
In Git Bash:
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```
The first `git clone` in Part B opens a browser window to sign in to GitHub. Sign in
and allow access. If no window opens, ask the repo owner to confirm you have access to
`rdhillbb/flushNcontinue`.

**A4. Install Claude Code.**
1. Open **PowerShell** (not Git Bash) and paste:
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
   It shows no progress while it downloads. Wait for the prompt to come back.
2. **Close PowerShell.** Open **Git Bash** and type:
   ```bash
   claude --version
   ```
   ✅ You see a version number, like `2.x.x (Claude Code)`.

   ❌ `command not found`: close every Git Bash window, open a new one, try again. If it
   still fails, see https://code.claude.com/docs/en/troubleshoot-install.
3. Type `claude` and follow the browser prompts to sign in. Then type `/exit`.

**A5. Only if Claude Code says it cannot find Git Bash:** open (or create)
`C:\Users\<you>\.claude\settings.json` in Notepad and add:
```json
{
  "env": {
    "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
  }
}
```
If the file already has content, add only the `"env"` part and keep the rest.

### Part B: Add flushNcontinue to a project (once per project, in Git Bash)

Replace `/c/Users/Paul/code/myproject` with your project's folder in every command.

**B1. Download flushNcontinue (first time only):**
```bash
mkdir -p ~/apps
git clone https://github.com/rdhillbb/flushNcontinue.git ~/apps/flushNcontinue
```
✅ The last line says `done.` and `ls ~/apps/flushNcontinue` lists `install.sh`.

**B2. Preview (changes nothing):**
```bash
bash ~/apps/flushNcontinue/install.sh /c/Users/Paul/code/myproject --dry-run
```
✅ You see `ok     python3 3.x`, `ok     Windows (Git Bash)`, some `do ...` lines, and at
the end `dry run: nothing was written.`

❌ A line starts with `STOP`: do what it says, then repeat B2. If you cannot fix it,
use [Part C](#part-c-manual-install-only-if-part-b-fails).

**B3. Install:**
```bash
bash ~/apps/flushNcontinue/install.sh /c/Users/Paul/code/myproject
```
✅ The end says `installed into /c/Users/Paul/code/myproject/.claude`.

**B4. Check:**
```bash
bash ~/apps/flushNcontinue/install.sh /c/Users/Paul/code/myproject --check
```
✅ The last line is `check: clean`.

**B5. Test the time-zone script:**
```bash
cd /c/Users/Paul/code/myproject
bash .claude/hooks/session_time.sh
```
✅ You see a **Session Time Reference** box with Cambodia, US Eastern and UTC times,
each one **different**.

❌ You see `⚠ This shell has no time-zone data`: Git Bash shows UTC for every zone.
Everything else still works. Use the UTC line as the true time, and tell Claude your
local time zone in your first message of each session.

**B6. Your personal rules (once per computer):**
```bash
mkdir -p ~/.claude
cp -n ~/apps/flushNcontinue/templates/personal-CLAUDE.md ~/.claude/CLAUDE.md
notepad ~/.claude/CLAUDE.md
```
In Notepad, replace the two `<fill in>` lines with your name and time zone
(for example `America/New_York`). Save and close.

**B7. The time script in `~/bin` (required, once per computer):**
Your rules and skills run `~/bin/session_time.sh` (on Windows:
`C:\Users\<you>\bin\session_time.sh`) at the start of every session. Copy it there:
```bash
mkdir -p ~/bin
cp ~/apps/flushNcontinue/claude/hooks/session_time.sh ~/bin/session_time.sh
bash ~/bin/session_time.sh
```
✅ You see the same **Session Time Reference** box as in B5.

**B8. Start Claude Code in the project:**
```bash
cd /c/Users/Paul/code/myproject
claude
```
✅ Before anything else you see the **Session Time Reference** box. Once the project has
a knowledge base you also see `=== SESSION BRIEF ===` and a `SESSION HEALTH` line.

If the project has no knowledge base yet, type `/kbinit` in Claude.

**B9. Share with the team** (skip if the project already has these committed):
```bash
git add .claude/skills .claude/hooks .claude/settings.json
git commit -m "Add flushNcontinue session memory"
```
Never commit `.claude/backups`.

### Part C: Manual install (only if Part B fails)

In Git Bash. Change the first line to your project folder.

**C1. Copy the files:**
```bash
P=/c/Users/Paul/code/myproject
mkdir -p "$P/.claude/skills" "$P/.claude/hooks"
cp -R ~/apps/flushNcontinue/claude/skills/checkpoint "$P/.claude/skills/"
cp -R ~/apps/flushNcontinue/claude/skills/flush      "$P/.claude/skills/"
cp -R ~/apps/flushNcontinue/claude/skills/kbinit     "$P/.claude/skills/"
cp ~/apps/flushNcontinue/claude/hooks/session-start.sh "$P/.claude/hooks/"
cp ~/apps/flushNcontinue/claude/hooks/pre-compact.sh   "$P/.claude/hooks/"
cp ~/apps/flushNcontinue/claude/hooks/session_time.sh  "$P/.claude/hooks/"
ls "$P/.claude/skills" "$P/.claude/hooks"
```
✅ The list shows `checkpoint flush kbinit` and the three `.sh` files.

**C2. Add the hooks.** Check whether the file exists:
```bash
ls "$P/.claude/settings.json"
```
- **`No such file`:** create it. Run `notepad "$P/.claude/settings.json"`, click **Yes**
  to create it, paste the block below exactly, save, close.
- **The file exists:** open it with `notepad "$P/.claude/settings.json"` and add the
  `"hooks"` part inside the outer `{ }`, with a comma after the item before it. If it
  already has a `"hooks"` part, ask for help rather than guess.

```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "", "hooks": [ { "type": "command", "shell": "bash",
        "command": "bash \"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/session-start.sh\"",
        "timeout": 60 } ] }
    ],
    "PreCompact": [
      { "matcher": "", "hooks": [ { "type": "command", "shell": "bash",
        "command": "bash \"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/pre-compact.sh\"",
        "timeout": 10 } ] }
    ]
  }
}
```

**C3. Check the file is valid:**
```bash
python3 -m json.tool "$P/.claude/settings.json" >/dev/null && echo "settings OK"
```
✅ You see `settings OK`. ❌ An error with a line number: fix the comma or bracket on that
line in Notepad, then run C3 again.

**C4. Verify, then continue with B5:**
```bash
bash ~/apps/flushNcontinue/install.sh "$P" --check
```
✅ `check: clean`. Then go back to **B5**.

### Windows problems and fixes

| What you see | Fix |
|---|---|
| `python3: command not found`, or the Store opens | Part A2, then close and reopen Git Bash |
| `claude: command not found` | Close all Git Bash windows, open a new one. Still failing: rerun Part A4 |
| Claude Code says it cannot find Git Bash | Part A5 |
| No **Session Time Reference** box when Claude starts | Start `claude` from Git Bash **inside** the project folder (B8). Run B4. |
| `$'\r': command not found` | A `.sh` file got Windows line endings. Do not edit `.sh` files in Notepad. Re-copy it (C1). |
| `⚠ This shell has no time-zone data` | Expected on some PCs; see B5 |
| `SESSION HEALTH` skips the port check | Expected: Git Bash has no `lsof` |
| `usage: bash install.sh <projectdir>` | The project folder is missing from the command; add it |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `usage: bash install.sh <projectdir>` | You left out the project folder. Add it, e.g. `bash ~/apps/flushNcontinue/install.sh ~/code/myproject`. |
| No time banner or `SESSION BRIEF` when Claude starts | Start `claude` **inside** the project folder. Run `install.sh <projectdir> --check`. Restart Claude Code. |
| `ok SessionStart: your personal ~/.claude/settings.json already does this` | Your own settings already run these hooks, so the project file does not get them. **Teammates then get no hooks.** If you will share the project, add the hooks to `.claude/settings.json` by hand (JSON in [Part C](#part-c-manual-install-only-if-part-b-fails), step C2). |
| `/checkpoint` or `/flush` is unknown | Check that `.claude/skills/checkpoint`, `flush` and `kbinit` exist in the project. If not, re-run `install.sh <projectdir>`. |
| `STOP … is not valid JSON` | `.claude/settings.json` has a typo. Fix it, then run Step 3 again. |
| `$'\r': command not found` (Windows) | A `.sh` file got CRLF endings. Re-copy it from the clone. |

---

## Undo

1. In the project, rename `.claude/skills/checkpoint`, `flush`, `kbinit` and
   `.claude/hooks/` (for example add `.old`).
2. Remove the `SessionStart` and `PreCompact` entries from `.claude/settings.json`, or
   restore the copy in `.claude/backups/flushNcontinue-<date>/settings.json`.
3. Restart Claude Code.

---

## Reference

### What gets installed (inside the project only)

| Location | What |
|---|---|
| `.claude/skills/` | `checkpoint`, `flush`, `kbinit` (copies; `kbinit/tools/` holds `kb_tools.py`, the engine behind flush) |
| `.claude/hooks/` | `session-start.sh`, `pre-compact.sh`, `session_time.sh` (the time-zone banner) |
| `.claude/settings.json` | Two hooks added; your other settings are kept. **SessionStart** prints the time and loads BRIEF; **PreCompact** saves the thread if a session compacts. |
| `.claude/backups/` | Old copies of anything replaced. Do not commit. |
| `~/bin/session_time.sh` | **Not done by the installer.** You copy it once per computer (Finish setup step 2, or Windows B7). |

### The knowledge files inside a project (created by `/kbinit`)

| File | Holds |
|---|---|
| `state/BRIEF.md` | Where the last session stopped: task, next step, open questions |
| `state/NOW.md` | What is true right now |
| `state/FINDINGS.md` | Open problems, one line each (`F-NN`) |
| `state/CONTRADICTIONS.md` | Docs known to be out of date (`C-NN`) |
| `docs/tribal/<year>-Q<n>.md` | Dated history. Append-only, never edited |
| Pitfalls file | Traps that cost time before (`P-NN`) |
| `KNOWLEDGE-MAP.md` | Where each fact lives, and which file wins |
| `scripts/kb/` | `kb_tools.py`, `kb_lint.sh`, `session_health.sh` |

**When files disagree:** the live system wins, then NOW, then CONTRADICTIONS, then FINDINGS.

**Branches:** these files are in git, so every branch has its own copy. Merge `main` into
your branch often. When they conflict, keep **both** sides' entries.

### What is in this repo

| Folder | Contents |
|---|---|
| `install.sh` | The installer (`<projectdir>`, `--dry-run`, `--check`) |
| `claude/skills/` | `checkpoint`, `flush`, `kbinit` (with its `procedures/`, `templates/`, `tools/`) |
| `claude/hooks/` | `session-start.sh`, `pre-compact.sh`, `session_time.sh` |
| `templates/` | `personal-CLAUDE.md` |
| `tests/` | `test_kb_tools.py` (run: `python3 -m pytest tests`) |
