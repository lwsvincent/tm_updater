# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Push

Remotes in this working copy (verified 2026-10-28):

- `origin` — `lwsvincent/tm_updater` (upstream). `aron0803` has **no push access** (403), so push elsewhere and open a PR.
- `fork` — `aron0803/tm_updater`. This is the push target; `main` tracks `fork/main`.
- `gitlab` — required by this file but **not configured** in this working copy. Add it with
  `git remote add gitlab <url>` before pushing there.

When pushing, push the current branch (and tags, if applicable) to every writable remote — currently `fork`, plus `gitlab` once configured.


