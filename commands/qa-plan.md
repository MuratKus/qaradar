---
description: Propose a prioritized test plan — what to test first and why
allowed-tools:
  - mcp__qaradar__qaradar_healthcheck
  - mcp__qaradar__qaradar_risky_modules
  - mcp__qaradar__qaradar_coverage_gaps
---

Run `qaradar_healthcheck`, then `qaradar_risky_modules`, then `qaradar_coverage_gaps` on $ARGUMENTS (default: current repo).

Produce a prioritized test plan:
1. **Immediate** — HIGH risk + no tests. 3–5 files with specific test ideas.
2. **Short-term** — HIGH risk + weak coverage. 3–5 files with gap descriptions.
3. **Maintenance** — MEDIUM risk, stable files. Mention only, don't over-specify.

Ground every item in real file paths and real reasons from the tool output. No generic advice.
