# flushNcontinue

**Claude Code remembers your project between sessions.**

Each session starts where the last one stopped, saves its progress as it works, and
hands off cleanly at the end. The memory lives in plain files inside the project, so
it is in git, reviewable, and shared with the team.

---

## What you get

- **A session that resumes.** On start, Claude reads the project's handoff file
  (`state/BRIEF.md`), tells you where things stopped, and asks "continue?".
- **A status line that tells you when to flush.** The bar at the bottom of Claude Code
  shows how full the context is and what to do: `ok`, `/checkpoint`, `FLUSH NOW`.
- **The date and time first.** Every session starts with a time banner
  (Cambodia, US Eastern, UTC), so Claude never guesses the day.
- **Three commands.**
  - `/checkpoint` saves the current thread in seconds.
  - `/flush` does the full end-of-session update.
  - `/kbinit` gives a new project its own memory.

The installer works on **one project at a time**. It copies the files into that
project's `.claude/` folder. A separate `--personal` run, once per computer, sets up the
two things that live in your home folder: `~/bin/session_time.sh` and the status line.

> **On Windows?** Skip to [Windows](#windows). It is a complete step-by-step guide from a
> new PC, set up by hand (no installer), and you do not need the Mac/Linux steps below.

---

## Before you start (Mac and Linux)

You need all of these:

- [ ] `git` (check: `git --version`)
- [ ] Python 3.9 or newer, runnable as `python3` (check: `python3 --version`)
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

**2. Personal setup: time script and status line (required, once per computer).**

```bash
bash ~/apps/flushNcontinue/install.sh --personal --dry-run
bash ~/apps/flushNcontinue/install.sh --personal
bash ~/apps/flushNcontinue/install.sh --personal --check
bash ~/bin/session_time.sh
```

✅ `check: clean`, then a **Session Time Reference** box with Cambodia, US Eastern and UTC
times.

This copies `~/bin/session_time.sh` (your rules and skills run it at the start of every
session) and the status line script, and adds the status line to `~/.claude/settings.json`.

If it says `you already have your own status line; NOT replaced`, your own status line
stays. See [The status line](#the-status-line) to switch.

**3. Restart Claude Code in the project**

```bash
cd ~/code/myproject
claude
```

✅ Claude Code opens, and at the bottom you see the status line, for example
`Opus | myproject | main | ctx --`.

The time banner is **not shown on screen**: Claude Code hands the start-up hook's output
to Claude only. To see it yourself, run `bash .claude/hooks/session-start.sh` in the
project, or ask Claude "What date and time did the session hook show?"

**4. New project: run `/kbinit` (required once per project).** If the project has no
`KNOWLEDGE-MAP.md` yet, type this in Claude:

```
/kbinit
```

Claude creates the knowledge files (`state/BRIEF.md`, `state/NOW.md`, `KNOWLEDGE-MAP.md`,
`docs/tribal/...`, `scripts/kb/...`). Then type `/exit` and start `claude` again.

✅ Claude's first reply restates where the last session stopped and asks
*"No issues? Then I continue with …"*. That means the hook loaded `state/BRIEF.md`.

If the project already has `KNOWLEDGE-MAP.md`, skip this step. Never run `/kbinit` on it.

**5. Share with the team.** Commit these from the project (not `.claude/backups`):

```bash
git add .claude/skills .claude/hooks .claude/settings.json .claude/.gitattributes
git add KNOWLEDGE-MAP.md AGENTS.md CLAUDE.md state docs/TribalKnowledge.md docs/tribal docs/buildout/04-KNOWN-PITFALLS.md scripts/kb
git commit -m "Add flushNcontinue session memory"
```

Teammates who pull the project get the project part. On their own computer they still do
steps 1 and 2 of [Finish setup](#finish-setup-3-minutes) (personal rules, time script,
status line).

---

## Daily use

| When | You do | What happens |
|---|---|---|
| **Start a session** | Nothing. Answer Claude's "continue?" | The hook gives Claude the time and BRIEF (not shown on screen) |
| **After each decision or finished step** | `/checkpoint` | The thread is saved into BRIEF (about 20 s). A crash loses nothing |
| **End of session, or context at 62%** | `/flush`, then start a new session | Knowledge files updated and committed locally |

**Claude cannot see its own context %.** The status line shows it to you. Nothing flushes
automatically: when it says `FLUSH NOW`, you type `/flush`.

### The status line

The line at the bottom of Claude Code looks like this:

```
Opus | myproject | main | ctx 64%  FLUSH NOW: /flush, then start a new session
```

It shows the model, the project, the git branch, and the context advice:

| Status line shows | What to do |
|---|---|
| `ctx 34%  ok` (green) | Keep working |
| `ctx 55%  /checkpoint after each decision` (yellow) | Type `/checkpoint` after every decision or finished step |
| `ctx 64%  FLUSH NOW: /flush, then start a new session` (red) | Finish the current step, type `/flush`, then `/exit` and start `claude` again |
| `ctx 71%  OVER LIMIT: /flush immediately, then new session` (red) | Type `/flush` now, then start a new session. Past 70% Claude makes more mistakes |
| `ctx --` | Normal at the start of a session, before the first reply |

**Where it comes from:** `~/.claude/settings.json` has
`"statusLine": {"type": "command", "command": "python3 ~/.claude/flushNcontinue/statusline.py"}`.
`install.sh --personal` adds it. Claude Code runs that script after each reply and shows
what it prints.

**You already had your own status line?** The installer does not replace it. To switch,
open `~/.claude/settings.json` and set the `statusLine` part to exactly:

```json
"statusLine": {
  "type": "command",
  "command": "python3 ~/.claude/flushNcontinue/statusline.py"
}
```

Then restart Claude Code. (Your old file is unchanged; keep a copy before editing.)

**No status line at all?** Run `bash ~/apps/flushNcontinue/install.sh --personal --check`
and restart Claude Code. Test the script by hand:

```bash
echo '{"context_window":{"used_percentage":64}}' | python3 ~/.claude/flushNcontinue/statusline.py
```

✅ It prints a line ending in `FLUSH NOW: /flush, then start a new session`.

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

Also refresh your personal part:

```bash
bash ~/apps/flushNcontinue/install.sh --personal
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

> **Not tested on Windows.** So on Windows everything is set up **by hand**, and
> `install.sh` is not used. The steps follow the official Claude Code Windows docs. If a
> step does not show the ✅ result, stop, copy the exact error text, and send it to the
> repo owner.

Do the parts in order: **A** and **B** once per computer, **C** once per project.

### Two windows you will use

| Window | How to open it | Its prompt looks like | Used for |
|---|---|---|---|
| **PowerShell** | Start menu → type `PowerShell` → open **Windows PowerShell** | `PS C:\Users\Paul>` | Only step A4 (installing Claude Code) |
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
3. Add time-zone data (Windows Python has none; `/kbinit` and `/flush` need it):
   ```bash
   python3 -m pip install --user tzdata
   python3 -c 'import zoneinfo; print(zoneinfo.ZoneInfo("America/New_York"))'
   ```
   ✅ The last line prints `America/New_York`.

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

### Part B: Set up by hand (once per computer, in Git Bash)

On Windows you set everything up **by hand**. Do not run `install.sh`: it has never been
tested on Windows. Every step below is a plain copy or a Notepad edit, with a ✅ check.

**B1. Download flushNcontinue (first time only):**
```bash
mkdir -p ~/apps
git clone https://github.com/rdhillbb/flushNcontinue.git ~/apps/flushNcontinue
ls ~/apps/flushNcontinue
```
✅ The list shows `README.md`, `claude`, `templates`.

**B2. The time script in `~/bin`:**
```bash
mkdir -p ~/bin
cp ~/apps/flushNcontinue/claude/hooks/session_time.sh ~/bin/session_time.sh
bash ~/bin/session_time.sh
```
✅ You see a **Session Time Reference** box with Cambodia, US Eastern and UTC times,
each one **different**.

❌ You see `⚠ This shell has no time-zone data`: Git Bash shows UTC for every zone.
Everything else still works. Use the UTC line as the true time, and tell Claude your
local time zone in your first message of each session.

**B3. The status line script:**
```bash
mkdir -p ~/.claude/flushNcontinue
cp ~/apps/flushNcontinue/claude/hooks/statusline.py ~/.claude/flushNcontinue/statusline.py
echo '{"context_window":{"used_percentage":64}}' | python3 ~/.claude/flushNcontinue/statusline.py
```
✅ It prints a line ending in `FLUSH NOW: /flush, then start a new session`.

**B4. Turn the status line on.** Check whether your personal settings file exists:
```bash
ls ~/.claude/settings.json
```
- **`No such file`:** run `notepad ~/.claude/settings.json`, click **Yes** to create it,
  paste this exactly, save, close:
  ```json
  {
    "statusLine": {
      "type": "command",
      "command": "python3 ~/.claude/flushNcontinue/statusline.py"
    }
  }
  ```
- **The file exists:** first keep a copy:
  `cp ~/.claude/settings.json ~/.claude/settings.json.old`. Then
  `notepad ~/.claude/settings.json` and add the `"statusLine"` part (the 4 middle lines
  above) inside the outer `{ }`, with a comma after the item before it. If it already
  has a `"statusLine"` part, replace only that part.

Check the file:
```bash
python3 -m json.tool ~/.claude/settings.json
```
✅ It prints the file back with no error. ❌ An error with a line number: fix the comma or
bracket on that line in Notepad, then check again.

**B5. Your personal rules:**
```bash
cp -n ~/apps/flushNcontinue/templates/personal-CLAUDE.md ~/.claude/CLAUDE.md
notepad ~/.claude/CLAUDE.md
```
In Notepad, replace the two `<fill in>` lines with your name and time zone
(for example `America/New_York`). Save and close.

### Part C: Add flushNcontinue to a project by hand (once per project, in Git Bash)

Change the first line to your project's folder, then paste the rest. Keep the same Git
Bash window open for C1 to C4 (they all use `$P`).

**C1. Copy the files into the project:**
```bash
P=/c/Users/Paul/code/myproject
F=~/apps/flushNcontinue
ls "$P/.claude/skills/flush" 2>/dev/null && echo "ALREADY INSTALLED: use C8 (update) instead"
mkdir -p "$P/.claude/skills" "$P/.claude/hooks"
cp -R "$F/claude/skills/checkpoint" "$F/claude/skills/flush" "$F/claude/skills/kbinit" "$P/.claude/skills/"
cp "$F/claude/hooks/session-start.sh" "$F/claude/hooks/pre-compact.sh" "$F/claude/hooks/session_time.sh" "$P/.claude/hooks/"
cp "$F/claude/gitattributes" "$P/.claude/.gitattributes"
ls "$P/.claude/skills" "$P/.claude/hooks"
```
✅ The list shows `checkpoint flush kbinit` and `pre-compact.sh session-start.sh
session_time.sh`. ❌ It printed `ALREADY INSTALLED`: stop and go to C8.

**C2. Add the two hooks to the project settings.** Check whether the file exists:
```bash
ls "$P/.claude/settings.json"
```
- **`No such file`:** run `notepad "$P/.claude/settings.json"`, click **Yes** to create
  it, paste the block below exactly, save, close.
- **The file exists:** keep a copy (`cp "$P/.claude/settings.json" "$P/.claude/settings.json.old"`),
  open it with `notepad "$P/.claude/settings.json"` and add the `"hooks"` part inside the
  outer `{ }`, with a comma after the item before it. If it already has a `"hooks"` part,
  ask for help rather than guess.

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

**C3. Check the settings file:**
```bash
python3 -m json.tool "$P/.claude/settings.json" >/dev/null && echo "settings OK"
grep -c "session-start.sh\|pre-compact.sh" "$P/.claude/settings.json"
```
✅ `settings OK`, then `2`. ❌ An error with a line number: fix the comma or bracket on
that line in Notepad, then run C3 again.

**C4. Test the hook by hand:**
```bash
cd "$P"
CLAUDE_PROJECT_DIR="$P" bash .claude/hooks/session-start.sh
```
✅ You see the **Session Time Reference** box (and, once C6 is done, `=== SESSION BRIEF ===`).

**C5. Start Claude Code in the project:**
```bash
cd "$P"
claude
```
✅ Claude Code opens, and at the bottom you see the status line, for example
`Opus | myproject | main | ctx --`. What each message means:
[The status line](#the-status-line).

The time banner is **not shown on screen**: Claude Code hands the start-up hook's output
to Claude only. To check, ask Claude "What date and time did the session hook show?"

**C6. New project: run `/kbinit` (once per project).** If the project has no
`KNOWLEDGE-MAP.md`, type `/kbinit` in Claude. When it finishes, type `/exit`, then run
`claude` again.

✅ Claude's first reply restates where things stopped and asks *"No issues? Then I continue
with …"*.

If the project already has `KNOWLEDGE-MAP.md`, skip this. Never run `/kbinit` on it.

**C7. Share with the team** (skip if the project already has these committed):
```bash
cd "$P"
git add .claude/skills .claude/hooks .claude/settings.json .claude/.gitattributes
git add KNOWLEDGE-MAP.md AGENTS.md CLAUDE.md state docs/TribalKnowledge.md docs/tribal docs/buildout/04-KNOWN-PITFALLS.md scripts/kb
git commit -m "Add flushNcontinue session memory"
```
Do not commit `settings.json.old` or `.claude/backups`.

The two `.gitattributes` files (`.claude/.gitattributes`, `scripts/kb/.gitattributes`) keep
the scripts in Unix line endings. Commit them: without them, Git for Windows changes the
`.sh` files on checkout and every hook fails with `$'\r': command not found`.

**A teammate who pulls a project that already has these files** does only Part A and
Part B on their own PC. Part C is already in the project.

**C8. Updating (when the repo owner says there is a new version).**
```bash
cd ~/apps/flushNcontinue && git pull
P=/c/Users/Paul/code/myproject
F=~/apps/flushNcontinue
OLD="$P/.claude/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OLD"
mv "$P/.claude/skills/checkpoint" "$P/.claude/skills/flush" "$P/.claude/skills/kbinit" "$P/.claude/hooks" "$OLD/"
printf '*\n' > "$P/.claude/backups/.gitignore"
mkdir -p "$P/.claude/hooks"
cp -R "$F/claude/skills/checkpoint" "$F/claude/skills/flush" "$F/claude/skills/kbinit" "$P/.claude/skills/"
cp "$F/claude/hooks/session-start.sh" "$F/claude/hooks/pre-compact.sh" "$F/claude/hooks/session_time.sh" "$P/.claude/hooks/"
cp "$F/claude/gitattributes" "$P/.claude/.gitattributes"
cp "$F/claude/hooks/session_time.sh" ~/bin/session_time.sh
cp "$F/claude/hooks/statusline.py" ~/.claude/flushNcontinue/statusline.py
ls "$P/.claude/skills" "$P/.claude/hooks"
```
✅ `git pull` ends with `Fast-forward` or `Already up to date.`, and the list shows the
same names as C1. The old copies are in `.claude/backups/` (never committed). Settings do
not change on an update. Restart `claude` in the project.

❌ `git pull` says `Your local changes ... would be overwritten`: you edited a file in
`~/apps/flushNcontinue`. Do not edit files there. Send the message to the repo owner.

Only one person commits the updated files to the project (agree who):
```bash
cd "$P"
git add .claude/skills .claude/hooks .claude/.gitattributes
git commit -m "Update flushNcontinue"
```

### Windows problems and fixes

| What you see | Fix |
|---|---|
| `python3: command not found`, or the Store opens | Part A2, then close and reopen Git Bash |
| `claude: command not found` | Close all Git Bash windows, open a new one. Still failing: rerun Part A4 |
| Claude Code says it cannot find Git Bash | Part A5 |
| `$P` is empty (`cp: missing destination`) | You opened a new Git Bash window. Run the `P=...` line again |
| Claude does not know the date, or does not restate the last session | Start `claude` from Git Bash **inside** the project folder (C5). Run C3 and C4. |
| `$'\r': command not found` | A `.sh` file got Windows line endings. Do not edit `.sh` files in Notepad. Copy it again from `~/apps/flushNcontinue` (C1 `cp` lines), and make sure both `.gitattributes` files are committed (C7). |
| `⚠ This shell has no time-zone data` | Expected on some PCs; see B2 |
| No status line at the bottom | Run B3 and the B4 check again, then restart Claude Code |
| Status line shows `ctx --` all the time | Normal before the first reply. If it stays after several replies, rerun the B3 `echo ...` test |
| `SESSION HEALTH` skips the port check | Expected: Git Bash has no `lsof` |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `usage: bash install.sh <projectdir>` | You left out the project folder. Add it, e.g. `bash ~/apps/flushNcontinue/install.sh ~/code/myproject`. |
| Claude does not know the date, or does not restate the last session | Start `claude` **inside** the project folder. Run `install.sh <projectdir> --check`. Run `bash .claude/hooks/session-start.sh` to see what the hook prints. Restart Claude Code. |
| `note SessionStart: your personal ~/.claude/settings.json also does this; on this computer it runs twice` | Harmless. The project still gets its own hooks, so teammates have them. To run it once on your computer, remove the same hook from `~/.claude/settings.json`. |
| `/checkpoint` or `/flush` is unknown | Check that `.claude/skills/checkpoint`, `flush` and `kbinit` exist in the project. If not, re-run `install.sh <projectdir>`. |
| `STOP … is not valid JSON` | `.claude/settings.json` has a typo. Fix it, then run Step 3 again. |
| `$'\r': command not found` (Windows) | See [Windows problems and fixes](#windows-problems-and-fixes). |

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
| `.claude/settings.json` | Two hooks added; your other settings are kept. **SessionStart** gives Claude the time and BRIEF; **PreCompact** prints the Live thread so the compaction summary can keep it (not guaranteed: flush at 62% instead). |
| `.claude/.gitattributes` | Keeps Unix line endings for everything in `.claude/`, so the bash hooks work on Windows. Commit it. |
| `.claude/backups/` | Old copies of anything replaced. Do not commit. |
| `~/bin/session_time.sh` | Only with `install.sh --personal` (once per computer). |
| `~/.claude/flushNcontinue/statusline.py` | Only with `--personal`. The flush status line script. |
| `~/.claude/settings.json` `statusLine` | Only with `--personal`, and only if you have no status line yet. |

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
| `install.sh` | The installer (`<projectdir>` or `--personal`; `--dry-run`, `--check`) |
| `claude/skills/` | `checkpoint`, `flush`, `kbinit` (with its `procedures/`, `templates/`, `tools/`) |
| `claude/hooks/` | `session-start.sh`, `pre-compact.sh`, `session_time.sh`, `statusline.py` |
| `templates/` | `personal-CLAUDE.md` |
| `tests/` | `test_kb_tools.py` (needs pytest: `python3 -m pip install --user pytest`, then `python3 -m pytest tests`) |
