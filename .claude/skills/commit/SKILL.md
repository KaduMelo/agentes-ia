---
name: commit
description: Stage changes and create a git commit following this project's standard workflow - review changes, confirm with the user, write an English Conventional Commits message. Use when the user says "commit", "commit isso", "faz um commit", or similar.
---

# Commit

Follow these steps in order. Do not skip the confirmation step.

1. Run `git status` and `git diff` (staged and unstaged) to see the full set of changes. Never use `-uall`.
2. Decide which files belong in this commit. Only include files relevant to the current logical change. Never stage files that look like secrets (`.env`, credentials, keys) without calling it out to the user first.
3. Show the user a short plan: the list of files you intend to `git add`, and the draft commit message. Do not run `git add` or `git commit` yet.
4. Write the commit message in **English**, following **Conventional Commits**:
   - Format: `<type>(<optional scope>): <short summary>`
   - Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `build`, `ci`
   - Summary in imperative mood, no trailing period, under ~70 chars on the subject line.
   - Add a body only if the "why" isn't obvious from the subject line.
5. Ask the user to confirm the file list and message (use AskUserQuestion or a direct question). Wait for explicit approval before proceeding.
6. Once confirmed: `git add <files>`, then commit with the approved message via a heredoc:
   ```bash
   git commit -m "$(cat <<'EOF'
   <type>: <summary>

   <optional body>
   EOF
   )"
   ```
7. Run `git status` after the commit to confirm success. If a pre-commit hook fails, fix the issue, re-stage, and create a new commit — never `--no-verify`.
8. Do not push and do not open a pull request — that is handled by the separate `pr` skill.
