# QA Radar

**Give your AI coding agent the quality brain it doesn't have to grow from scratch.**

QA Radar analyzes your codebase and produces a structured quality health report — combining git churn, test coverage, and test-to-source mapping into risk-scored modules. It works as an **MCP server** for AI coding agents (Claude Code, Cursor, Windsurf) and as a **standalone CLI** for humans and CI pipelines.

Built for developers who want their AI agent to write *targeted* tests, not generic ones.

## What It Does

QA Radar answers the question every new team member (and every AI agent) asks: **"What should I test first?"**

It scans three signals and combines them into a per-file risk score:

| Signal | What It Measures | Why It Matters |
|--------|-----------------|----------------|
| **Git Churn** | Commit frequency, lines changed, recency | High-churn files are regression magnets |
| **Coverage Gaps** | Line & branch coverage from existing reports | Low coverage = blind spots |
| **Test Mapping** | Which source files have corresponding tests | No tests = no safety net at all |

The output is a ranked list of modules by risk level (critical → low), with human-readable reasons for each rating.

## Why Not Just Let the Agent Do It?

A capable agent with bash access could run `git log --numstat`, parse `coverage.xml`, and glob for test files. So why an MCP server?

| Concern | What QA Radar does instead |
|---------|---------------------------|
| **Token cost** | `git log` over 90 days on a medium repo is hundreds of KB. QA Radar returns ~5 KB of structured JSON. |
| **Determinism** | A weighted risk score computed ad-hoc in-context is unreliable. Code is reproducible. |
| **Speed** | One tool call vs. 4–6 sequential bash calls + reasoning between each. |
| **Format normalization** | LCOV / Cobertura / coverage.py JSON / Go cover profiles all parse differently. QA Radar normalizes across formats so the agent doesn't have to. |
| **Convention encoding** | `test_x.py` for Python, `x.test.ts` for JS/TS, `x_test.go` for Go, `FooTest.java` for Java — encoded once, not re-derived each session. |
| **Portability** | The same MCP tools work across Claude Code, Cursor, and Windsurf without re-prompting. |

## MCP Server (for AI Coding Agents)

### Setup

Add to your Claude Code config (`~/.claude/claude_desktop_config.json`):

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

Or start it manually:

```bash
qaradar serve
```

### Example Prompts

Once connected, ask your agent:

> "What should I test first in this repo?"
> "Which files are the riskiest right now?"
> "Show me the highest-churn files from the last month."
> "Which source files have no tests at all?"

### Available MCP Tools

| Tool | When the Agent Uses It |
|------|------------------------|
| `qaradar_healthcheck` | Full quality overview of a repository |
| `qaradar_risky_modules` | What to test first; which files are riskiest |
| `qaradar_churn` | Hotspot detection; where regressions tend to occur |
| `qaradar_coverage_gaps` | Files with low coverage; where the blind spots are |
| `qaradar_untested_files` | Source files with no corresponding test files |

## CLI

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

## Install

Install from source:

```bash
git clone https://github.com/murat/qaradar.git
cd qaradar
pip install -e .
```

> PyPI release coming in v0.1.1.

## Language Support

### Tier 1 — First-class, tested

| Language | Test detection | Coverage |
|----------|---------------|---------|
| Python | `test_x.py`, `x_test.py` | coverage.py JSON + XML |
| JavaScript / TypeScript | `x.test.{js,ts,jsx,tsx}`, `x.spec.*` | LCOV |
| Go | `x_test.go` | Go cover profile (`cover.out`) |

### Tier 2 — Best-effort, naming-based

Java, Kotlin, Ruby, Swift, Rust — test detection via naming conventions, not extensively tested. Coverage via Cobertura XML or LCOV if emitted.

> Coverage parsing is format-driven (Cobertura / LCOV / coverage.py / Go profile), so it spans more ecosystems than test-mapping detection, which is language-specific.

## Supported Coverage Formats

| Format | Tools |
|--------|-------|
| coverage.py JSON | Python `coverage run` + `coverage json` |
| Cobertura XML | Python, Java/Gradle, .NET (Coverlet) |
| LCOV | JS/TS (Jest/Vitest/Istanbul), C/C++, Rust (grcov) |
| Go cover profile | `go test -coverprofile=cover.out` |

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

- [ ] **v0.1.2** — Claude Code plugin + slash commands (`/qa-check`, `/qa-untested`)
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
