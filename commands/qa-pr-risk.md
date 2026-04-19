---
description: Show which files changed in this PR are riskiest — by churn, coverage, and test mapping
allowed-tools:
  - mcp__qaradar__qaradar_pr_risk
---

Call `qaradar_pr_risk` on $ARGUMENTS (default: current repo, auto-detected base branch).

Summarise the headline (e.g. "3 of 8 changed source files are HIGH+ risk"), then list the HIGH and CRITICAL changed files with the top reason each scored high. Call out any changed files that have no tests — these are the most urgent.  Keep it to one focused paragraph per risk bucket.
