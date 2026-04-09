---
name: delegation
description: Break work into parallel or specialized sub-tasks when the host supports sub-agents. Use when the request has independent workstreams or needs a focused secondary pass.
---

# Delegation

Use this skill when:
- The task has independent workstreams.
- A second pass would materially reduce risk.
- The host supports sub-agents or delegated workers.

Rules:
1. Keep the critical path local.
2. Give each delegate a concrete scope and disjoint write set.
3. Pass only the context needed for that sub-task.
4. Integrate results and run final validation in the main thread.
