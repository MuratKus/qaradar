---
description: List source files with no detected tests
allowed-tools:
  - mcp__qaradar__qaradar_untested_files
---

Call `qaradar_untested_files` on $ARGUMENTS (default: current repo).

Filter out trivial files (e.g. `__init__.py` under 10 lines, pure type stubs). Rank the remaining by apparent complexity/size and suggest a test scaffold for the top 3.
