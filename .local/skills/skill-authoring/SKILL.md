---
name: skill-authoring
description: Create or update repo-local skills under `.local/skills` or `.local/secondary_skills`. Use when the user wants reusable agent instructions added, cleaned up, or documented.
---

# Skill Authoring

Use this skill when:
- The user wants reusable instructions stored in the repo.
- An existing skill needs cleanup, renaming, or metadata repair.
- The catalog or bridge files need to stay in sync.

Rules:
1. Canonical roots are `.local/skills` and `.local/secondary_skills`.
2. Skill folder names and frontmatter `name` values must be lowercase hyphen-case.
3. Every skill folder must contain `SKILL.md` and `agents/openai.yaml`.
4. After changes, run [the validator script](../../../scripts/validate_skill_catalog.py) in write mode.
