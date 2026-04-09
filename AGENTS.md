# Repo Skill Registry

The canonical skill catalogs for this repository live in `.local/skills` and `.local/secondary_skills`.

Before starting any multi-step work:
1. Read `.local/skill-index.md`.
2. Prefer `.local/skills` for 4tie-specific repo work.
3. Use `.local/secondary_skills` only for portable extras that do not need to be repo-owned primaries.
4. Keep skill folder names and frontmatter `name` values in lowercase hyphen-case.

Do not maintain a mirrored host-specific skill tree. Hosts should read the canonical markdown in place and use each skill folder's `agents/openai.yaml` only as host metadata.
