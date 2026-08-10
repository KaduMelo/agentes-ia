---
name: pr
description: Push the current feature/** branch and open a GitHub pull request into develop, following this project's branching convention. Use when the user says "abre um PR", "open a PR", "cria o pull request", or similar.
---

# Open PR (feature/** -> develop)

This project's convention: work happens on branches named `feature/**`, and pull requests always target `develop` (never `main` directly).

1. Run `git branch --show-current`. If the branch name does not start with `feature/`, stop and tell the user — ask whether they want to rename/create a proper `feature/**` branch first, rather than opening the PR from the wrong branch.
2. Run `git status` and `git log --branches --not --remotes` (or compare against `origin/develop`) to confirm there are commits ready to go up. If there's nothing committed, tell the user to commit first (point them at the `commit` skill).
3. Check whether `develop` exists on the remote: `git ls-remote --heads origin develop`. If it doesn't exist yet, tell the user and ask whether to create it (e.g. from `main`) before opening the PR — do not silently invent a base branch.
4. Confirm with the user before doing anything that touches the remote: show the branch name, the base (`develop`), and the list of commits that will be included.
5. Once confirmed:
   - Push the branch: `git push -u origin <branch>` (only if not already up to date with the remote).
   - Create the PR with `gh pr create --base develop --head <branch> --title "..." --body "..."`. Title should summarize the change (Conventional Commits style is fine, e.g. `feat: ...`). Body should have a short Summary section and a Test plan checklist, generated from the actual commits/diff on the branch — not boilerplate.
6. Return the PR URL to the user.

Never force-push, never target `main`, and never skip the confirmation step before pushing or creating the PR.
