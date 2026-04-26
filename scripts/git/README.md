# Git Guardrails

## Large file blocker

This repository includes a pre-commit hook that blocks staged files larger than `20 MB` by default.

- Hook file: `.githooks/pre-commit`
- Checker: `scripts/git/check_large_files.py`

You can customize the threshold:

```bash
GIT_MAX_FILE_MB=50 git commit -m "your message"
```

## One-time setup

Run in repository root:

```bash
git config core.hooksPath .githooks
```
