---
name: ship-feature
description: Test, commit, push, create a PR, squash merge, and clean up after a feature is complete
disable-model-invocation: true
allowed-tools:
  - Read
  - Bash
  - mcp__github__create_pull_request
  - mcp__github__merge_pull_request
  - mcp__github__delete_branch
---

# Ship feature

## Rules

- Run the steps in order.
- If any command or tool call fails, stop immediately, report the error, and do not continue.
- Never delete a local or remote branch unless the PR merge has been confirmed.
- Never force-push.
- Never mark a definition-of-done item as complete unless it has been verified.
- Shell variables may not persist between Bash calls. Use the literal branch name, repository, and PR number in later steps.

## Step 1 — Run preflight checks

Run:

```bash
git branch --show-current
git remote get-url origin
git fetch origin main
git status -s
git log origin/main..HEAD --oneline
```

Remember:

- The current branch name as `<branch>`
- The GitHub owner and repository name from the remote URL as `<owner>` and `<repo>`

Stop if:

- The branch name is empty, which means Git is in a detached HEAD state
- The branch is `main`
- The working tree is clean and the branch has no commits ahead of `origin/main`

Report: `✓ Preflight passed — <branch>`

## Step 2 — Run tests

Run:

```bash
python -m pytest
```

Stop if any test fails. If pytest finds no tests or is not installed, stop and ask the user whether to continue.

Report: `✓ Tests passed`

## Step 3 — Review changes and find the spec

Run:

```bash
git status -s
git diff --staged
git diff
git log origin/main..HEAD --oneline
git diff --name-only origin/main...HEAD
ls -1 .claude/specs/
```

Read the spec in `.claude/specs/` that matches this feature. If no spec clearly matches, or several could match, stop and ask the user which one to use.

Check every changed and untracked file. Stop and ask the user before including:

- Secrets or credentials, including `.env` files
- Local databases
- Logs, caches, build output, or virtual environments
- Files unrelated to this feature

## Step 4 — Verify the definition of done

Check each definition-of-done item in the spec against the code, the test results, or by running the relevant check.

If any item fails or cannot be verified, stop and list those items. Do not commit, create a PR, or merge until the user decides what to do.

Report: `✓ Definition of done verified`

## Step 5 — Commit

Skip this step if the working tree is clean and report: `✓ No new commit needed`

Generate a Conventional Commit message:

- `feat:` new feature
- `fix:` bug fix
- `chore:` config or tooling
- `docs:` documentation only

Message rules:

- Lowercase
- No period at the end
- Under 72 characters
- Describes what the user can now do, not what the code does
  - **Good:** `feat: add delete expense button with confirmation dialog`
  - **Bad:** `feat: added DELETE route to app.py`

Stage only the files reviewed in Step 3 by naming each path explicitly. Do not use `git add .` or `git add -A`.

Run:

```bash
git add -- <file-1> <file-2>
git diff --staged --name-only
git commit -m "<generated-message>"
```

Report: `✓ Committed — <message>`

## Step 6 — Push the feature branch

Run:

```bash
git push -u origin <branch>
```

Report: `✓ Pushed — <branch>`

## Step 7 — Create the PR

Run:

```bash
git diff --name-only origin/main...HEAD
```

Use `mcp__github__create_pull_request` to create a PR from `<branch>` into `main` in `<owner>/<repo>`.

- **Title:** Plain English feature name with no Conventional Commit prefix, such as `Add delete expense functionality`
- **Description:**

```markdown
## What this PR does
<one paragraph from the spec overview section>

## Changes
<bullet list of every changed file with a one-line description>

## Definition of done
<the checklist from the spec, with verified items marked [x]>

## How to test
1. Run `python app.py`
2. Log in as demo@spendly.com / demo123
3. <specific steps from the spec to verify this feature>
```

Remember the PR number as `<pr-number>`.

Report: `✓ PR created — <PR URL>`

## Step 8 — Merge the PR

Use `mcp__github__merge_pull_request` to merge PR `<pr-number>` in `<owner>/<repo>` with the merge method set to `squash`.

Stop if GitHub reports merge conflicts, failing required checks, or a required review. Keep both branches and give the user the PR URL.

Report: `✓ PR merged to main`

## Step 9 — Delete the remote branch

Use `mcp__github__delete_branch` to delete `<branch>` from `<owner>/<repo>`.

If that tool is unavailable, run:

```bash
git push origin --delete <branch>
```

If GitHub has already deleted the branch automatically, treat this step as complete.

Report: `✓ Remote branch deleted`

## Step 10 — Switch to main and update it

Run:

```bash
git checkout main
git pull --ff-only origin main
```

Report: `✓ Switched to main — up to date`

## Step 11 — Delete the local branch

The merge was confirmed in Step 8. A squash merge can make Git treat the branch as unmerged, so use `-D`:

```bash
git branch -D <branch>
```

Report: `✓ Local branch deleted`

## Final summary

Print:

```text
Feature shipped
Branch:  <branch> (deleted locally and remotely)
Commit:  <commit message, or "no new commit">
PR:      <PR URL>
Tests:   passed
Status:  merged to main with squash
```