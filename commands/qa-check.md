---
description: Run a full QA health check and summarize risk, coverage, and untested files
allowed-tools:
  - mcp__qaradar__qaradar_healthcheck
---

Run `qaradar_healthcheck` on $ARGUMENTS (default: current repo).

Summarize in this order:
1. Top 3 risky modules with the specific reason each is risky
2. Coverage status (or "no coverage data" if missing)
3. Files with no tests
4. One concrete suggestion for where to focus testing next

Be specific — reference real file paths from the tool output, not generic advice.
