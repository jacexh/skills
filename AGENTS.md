# Agent Instructions

This repository is a collection of reusable AI agent skills. Each skill is a self-contained directory under `skills/` with a `SKILL.md` file and optional supporting files.

## Repository Structure

```
skills/
  <skill-name>/
    SKILL.md           # Required: skill instructions
    scripts/           # Optional: helper scripts (Python)
    references/        # Optional: reference documents
    assets/            # Optional: images, templates, other static files
resources/             # Shared assets used across multiple skills
```

## SKILL.md Format

Every `SKILL.md` must begin with a YAML frontmatter block:

```yaml
---
name: <skill-name>          # Required: matches the directory name exactly
description: <description>  # Required: one sentence; start with "Use when..."
version: 1.0.0              # Optional: semver, increment on breaking changes
updated: YYYY-MM-DD         # Optional: date of last significant update
---
```

**Frontmatter rules:**
- `name` must exactly match the directory name (e.g., directory `skills/tdd/` → `name: tdd`)
- `description` must be a single line; include trigger conditions ("Use when...")
- `version` follows semver; omit if not tracking versions
- No other frontmatter fields are used

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Skill directory | `kebab-case` | `skills/python-error-handling/` |
| `name` field | same as directory | `name: python-error-handling` |
| `SKILL.md` | always uppercase | `SKILL.md` |
| Script files | `snake_case.py` | `scripts/merge_videos.py` |

**Directory naming guidelines:**
- Language-specific skills: prefix with the language (`python-`, `golang-`, `react-`)
- General/methodology skills: no prefix (`tdd`, `brainstorming`, `api-design`)
- Keep names short and descriptive; no abbreviations unless universally known

## Adding a New Skill

1. Create `skills/<skill-name>/` — directory name in `kebab-case`
2. Add `SKILL.md` with correct frontmatter (`name` matches directory)
3. Write skill content in Markdown; include "When to Use", examples, and best practices
4. Add an entry to `README.md` under the appropriate category section
5. If scripts are needed, add them to `skills/<skill-name>/scripts/` in Python

## Scripts Language Requirement

All scripts in `scripts/` directories **must be written in Python** (minimum Python 3.11).

- Use the standard library where possible; avoid unnecessary third-party dependencies
- If external packages are required, document them in a comment at the top of the script
- Scripts must be runnable standalone: `python scripts/<script_name>.py`
- Do not add shell scripts (`.sh`), JavaScript, or other languages — Python only

```python
#!/usr/bin/env python3
"""
Script description.

Requirements: ffmpeg (system), tqdm>=4.0 (pip)
Usage: python scripts/example.py <input> <output>
"""
```

## README.md Updates

When adding a skill, append it to the correct category in `README.md`:

```markdown
- [skill-name](skills/skill-name/SKILL.md): One-line description matching the frontmatter.
```

Categories (in order): Go, Python, Frontend, API & Database, General. Add a new category only if none of the existing ones fit.

## What Not to Do

- Do not add build systems, package managers, or CI configuration unless specifically requested
- Do not create top-level files other than `README.md`, `AGENTS.md`, `CLAUDE.md`, and `LICENSE`
- Do not modify existing skills unless fixing a factual error or updating outdated content
- Do not add `node_modules/`, `__pycache__/`, `.venv/`, or other generated directories
