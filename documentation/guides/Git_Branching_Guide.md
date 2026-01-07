# Git Branching Strategy Guide

## Overview

This project uses a feature branch strategy to organize two parallel streams of work:

1. **Phase 0**: Refactoring existing Python replay scripts
2. **Phases 1-7**: VBA to Python migration

## Branch Structure

```md
main (stable, production-ready code)
├── phase0-refactoring (all replay script refactoring work)
└── vba-migration (VBA conversion work - created after Phase 0 completes)
```

## Setup Commands

### Initial Configuration (Do This Once)

```bash
# Configure git to rebase instead of merge when pulling
# This prevents unnecessary merge commits and keeps history clean
git config --global pull.rebase true

# Or configure just for this repository:
git config pull.rebase true
```

### Creating Phase 0 Branch (Do This Now)

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create and switch to Phase 0 refactoring branch
git checkout -b phase0-refactoring

# Push the new branch to remote
git push -u origin phase0-refactoring
```

### Working on Phase 0

```bash
# Make sure you're on the right branch
git branch  # Should show * phase0-refactoring

# Make your changes, then stage them
git add .

# Commit with descriptive message
git commit -m "Refactor phase_2_processor to use txr_replay_core"

# Push changes to remote
git push origin phase0-refactoring

# Commit regularly as you make progress
git add python/phase_2_processor_v4_0.py
git commit -m "Add CLI interface to phase_2_processor"
git push origin phase0-refactoring
```

### Viewing Your Work

```bash
# See what branch you're on
git branch

# See what's changed
git status

# See commit history
git log --oneline

# Compare your branch to main
git diff main..phase0-refactoring
```

### When Phase 0 is Complete

```bash
# Make sure all changes are committed
git status  # Should show "nothing to commit"

# Switch back to main
git checkout main

# Pull any updates (in case main changed)
git pull origin main

# Merge Phase 0 branch into main
git merge phase0-refactoring

# Push updated main to remote
git push origin main

# Optional: Delete the Phase 0 branch (if you want to clean up)
git branch -d phase0-refactoring
git push origin --delete phase0-refactoring
```

### Creating VBA Migration Branch (After Phase 0)

```bash
# Start from updated main
git checkout main
git pull origin main

# Create VBA migration branch
git checkout -b vba-migration

# Push to remote
git push -u origin vba-migration
```

## Workflow Best Practices

### Commit Messages

Use clear, descriptive commit messages:

**Good**:

- `"Create txr_replay_core package with shared utilities"`
- `"Refactor phase_2_processor to use ConfigManager"`
- `"Add CLI interface to phase_3_processor"`
- `"Extract DateParser to shared library"`
- `"Add 35 unit tests for core library (100% pass)"`

**Bad**:

- `"Fixed stuff"`
- `"Updates"`
- `"WIP"`

### Commit Frequency

Commit frequently with logical chunks:

- After completing a module
- After tests pass
- Before trying something experimental
- At the end of each work session

### Example Phase 0 Workflow

```bash
# Day 1: Create core library
git checkout phase0-refactoring
# ... create txr_replay_core files ...
git add txr_replay_core/
git commit -m "Create txr_replay_core package with data structures and utils"
git push origin phase0-refactoring

# ... create tests ...
git add tests/test_core/
git commit -m "Add 35 unit tests for core library"
git push origin phase0-refactoring

# Day 2: Refactor Phase 2
git checkout phase0-refactoring
# ... refactor phase_2_processor ...
git add python/phase_2_processor_v4_0.py
git commit -m "Refactor phase_2_processor to use txr_replay_core"
git push origin phase0-refactoring

# ... add CLI interface ...
git add python/phase_2_processor_v4_0.py
git commit -m "Add CLI interface to phase_2_processor"
git push origin phase0-refactoring

# Day 3: Refactor Phase 3
# ... continue with phase_3_processor ...
git add python/phase_3_processor_v5_0.py
git commit -m "Refactor phase_3_processor to use shared DateParser"
git push origin phase0-refactoring
```

## Troubleshooting

### If Your History Has Unnecessary Merge Commits

Merge commits from improper push/pull/sync can clutter your history. Here's how to clean them up:

```bash
# 1. Create a backup branch first
git branch phase0-refactoring-backup

# 2. Find the commit before the messy merges started
git log --oneline --graph -20

# 3. Interactive rebase from that commit (e.g., abc1234)
git rebase -i abc1234

# 4. In the editor, keep 'pick' for all real commits, 
#    the merge commits will be automatically removed

# 5. Force push the cleaned history
git push --force-with-lease origin phase0-refactoring
```

**Prevention**: The `pull.rebase true` configuration prevents these merge commits from occurring in the first place.

### If You Forgot to Create a Branch

```bash
# If you made changes on main by mistake
git stash  # Temporarily save your changes
git checkout -b phase0-refactoring  # Create branch
git stash pop  # Restore your changes
git add .
git commit -m "Your commit message"
git push -u origin phase0-refactoring
```

### If You Want to Undo Last Commit

```bash
# Undo last commit but keep changes
git reset --soft HEAD~1

# Undo last commit and discard changes (careful!)
git reset --hard HEAD~1
```

### If You Want to See What Changed

```bash
# See what files changed in last commit
git show --name-only

# See detailed changes in last commit
git show

# Compare your branch to main
git diff main
```

### If You Need to Pull Latest Main Into Your Branch

```bash
# On your phase0-refactoring branch
git checkout phase0-refactoring

# Pull latest main and merge it
git pull origin main

# If there are conflicts, resolve them, then:
git add .
git commit -m "Merge latest main into phase0-refactoring"
git push origin phase0-refactoring
```

## Quick Reference

| Task | Command |
| ------ | --------- |
| Check current branch | `git branch` |
| Switch branch | `git checkout branch-name` |
| Create and switch | `git checkout -b new-branch-name` |
| See changes | `git status` |
| Stage all changes | `git add .` |
| Stage specific file | `git add path/to/file.py` |
| Commit | `git commit -m "message"` |
| Push | `git push origin branch-name` |
| Pull | `git pull origin branch-name` |
| View history | `git log --oneline` |
| Compare to main | `git diff main` |

## Current Status

- ✅ `main`: Stable code with txr_replay_core package
- 🚧 `phase0-refactoring`: To be created - will contain all refactoring work
- ⏳ `vba-migration`: To be created after Phase 0 completes

## Next Steps

1. **Now**: Create `phase0-refactoring` branch
2. **Phase 0 Work**: All refactoring commits go to `phase0-refactoring`
3. **After Phase 0**: Merge to `main`, then create `vba-migration` branch
4. **VBA Work**: All VBA conversion commits go to `vba-migration`

## Questions?

- **Should I commit after every change?** - Commit logical chunks (a completed feature, passing tests)
- **How often should I push?** - Push at least daily, or after significant milestones
- **What if I break something?** - That's why we have branches! You can always revert or reset
- **Can I work on VBA while refactoring?** - Yes, but keep them in separate branches

## Resources

- [Git Branching Basics](https://git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell)
- [Feature Branch Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow)
