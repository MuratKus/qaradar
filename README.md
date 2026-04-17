# QA Radar

**Point it at a repo, get the quality landscape.**

QA Radar analyzes your codebase and produces a structured quality health report — combining git churn, test coverage, and test-to-source mapping into risk-scored modules. It works as a **standalone CLI**, an **MCP server** for AI coding agents (Claude Code, Cursor, Copilot), or a **CI integration** that comments quality briefs on PRs.

Built for QA leaders and developers who need to know *where* quality attention is needed most — not just "write more tests."

## What It Does

QA Radar answers the question every new team member asks: **"What should I test first?"**

It scans three signals and combines them into a per-file risk score:

| Signal | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Git Churn** | Commit frequency, lines changed, recency | High-churn files are regression magnets |
| **Coverage Gaps** | Line & branch coverage from existing reports | Low coverage = blind spots |
| **Test Mapping** | Which source files have corresponding tests | No tests = no safety net at all |

The output is a ranked list of modules by risk level (critical → low), with human-readable reasons for each rating.

## Install

```bash
pip install qaradar
```

Or install from source:

```bash
git clone https://github.com/murat/qaradar.git
cd qaradar
pip install -e .
```

## Usage

### CLI

```bash
# Full health check on current directory
qaradar analyze

# Analyze a specific repo with 180 days of history
qaradar analyze /path/to/repo --days 180

# Output as JSON (for piping to other tools)
qaradar analyze --json-output

# Show top 10 risky modules only
qaradar analyze --top 10
```

### MCP Server (for AI Coding Agents)

Start the server:

```bash
qaradar serve
```

Or add to your Claude Code config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "qaradar": {
      "command": "qaradar",
      "args": ["serve"]
    }
  }
}
```

Then in Claude Code:

> "What are the riskiest modules in this repo?"
> "Which files have no tests?"
> "Show me the highest churn files from the last month"

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `qaradar_healthcheck` | Full quality health report |
| `qaradar_risky_modules` | Find modules with highest quality risk |
| `qaradar_churn` | Git churn analysis (hotspot detection) |
| `qaradar_coverage_gaps` | Files below coverage threshold |
| `qaradar_untested_files` | Source files with no corresponding tests |

## Supported Formats

**Coverage reports:** coverage.py JSON, coverage.py XML, Cobertura XML, LCOV

**Languages (test detection):** Python, JavaScript/TypeScript, Java, Kotlin, Go, Ruby, Swift, Rust

**Git:** Any git repository

## Example Output

```
╭──────────────── QA Radar Health Report ─────────────────╮
│ Repository: /home/user/my-service                       │
│ Source files: 47  Test files: 23  Ratio: 0.49           │
│ Avg coverage: 62.3%  Tested: 31  Untested: 16          │
╰─────────────────────────────────────────────────────────╯

  CRITICAL risk modules: 3
  HIGH risk modules: 7

┌─────────────────────────────────────────────────────────┐
│ Risky Modules                                           │
├──────────────────────┬──────────┬───────┬───────────────┤
│ File                 │ Risk     │ Score │ Reasons       │
├──────────────────────┼──────────┼───────┼───────────────┤
│ src/payments/core.py │ CRITICAL │  0.87 │ High churn:   │
│                      │          │       │ 34 commits;   │
│                      │          │       │ No tests      │
│ src/auth/tokens.py   │ CRITICAL │  0.82 │ Low coverage: │
│                      │          │       │ 12.3%; Active │
│                      │          │       │ recently      │
└──────────────────────┴──────────┴───────┴───────────────┘
```

## Roadmap

- [ ] **v0.2** — Diff-aware mode: analyze only changed files in a PR
- [ ] **v0.3** — CI integration: GitHub Action that posts quality briefs on PRs
- [ ] **v0.4** — Flaky test detection from CI history (JUnit XML parsing)
- [ ] **v0.5** — Exploratory charter generation from diff + risk data
- [ ] **v1.0** — Historical trend tracking and quality regression alerts

## Philosophy

QA Radar is built on three beliefs:

1. **The bottleneck has moved.** AI makes writing tests easy. Knowing *which* tests matter is the hard part.
2. **Quality is a landscape, not a number.** A single coverage percentage hides everything. Risk is per-module, per-signal, per-timeframe.
3. **Agents need context.** An AI coding assistant that doesn't know your repo's fragile areas will write generic tests. Give it the quality landscape and it writes targeted ones.

## License

MIT
