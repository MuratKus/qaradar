---
description: Find the riskiest files in the repo — high churn, low coverage, missing tests
allowed-tools:
  - mcp__qaradar__qaradar_risky_modules
---

Call `qaradar_risky_modules` on $ARGUMENTS (default: current repo).

Group results by risk level (HIGH/MEDIUM/LOW). For each HIGH-risk file, explain the top 1–2 reasons it scored high and recommend whether to add tests, increase coverage, or refactor. Keep it tight.
