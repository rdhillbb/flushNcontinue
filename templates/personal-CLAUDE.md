# Personal instructions (Claude Code, all projects)

Written by flushNcontinue/install.sh because this file did not exist. Edit freely; the
installer never overwrites it. Project rules live in each repo's AGENTS.md / CLAUDE.md.

## Who I am
- Name / role: <fill in>
- My time zone: <fill in, e.g. America/New_York>

## Session start
- Run `bash ~/bin/session_time.sh` first. Never guess the date or the day of the week.

## Knowledge base (repos with KNOWLEDGE-MAP.md)
- The SessionStart hook injects `state/BRIEF.md`. Follow the resume protocol it prints.
- `/checkpoint` after every decision and every finished step.
- Context: at 50% checkpoint at every decision point; at 62% finish the step, run `/flush`,
  and end the session ("flushed at NN%, start a new session"); never past 70%.
  Claude cannot see its own context %. I read it in the status bar and say "flush";
  until then, checkpoint after every finished step.
- `/flush` commits the KB files by name. It never pushes.

## Working rules
- When a request is unclear, ask first. Never guess.
- Never write a secret into any file. Key name + "fetch live" only.
- Push and deploy only with explicit approval for those specific commits.
