# QA Radar

**Give your AI coding agent the quality brain it doesn't have to grow from scratch.**

QA Radar analyzes your codebase and produces a structured quality health report — combining git churn, test coverage, and test-to-source mapping into risk-scored modules. It works as an **MCP server** for AI coding agents (Claude Code, Cursor, Windsurf) and as a **standalone CLI** for humans and CI pipelines.

Built for developers who want their AI agent to write *targeted* tests, not generic ones.

## Quick Start

**Claude Code — one step:**

```
/plugin marketplace add Muratkus/qaradar
/plugin install qaradar@qaradar-marketplace
```

Then ask your agent: _"What should I test first?"_

Or run directly without installing:

```bash
uvx qaradar serve
```

[Full install options ↓](#install-as-claude-code-plugin-recommended)

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

## Install as Claude Code Plugin (Recommended)

The fastest path — one command wires up the MCP server and installs 4 slash commands. No manual config editing.

**Step 0 — install uv** (if you don't have it):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv
```

uv launches qaradar on demand from PyPI — you don't need to `pip install qaradar` separately.

**Step 1 — add the marketplace:**

```
/plugin marketplace add Muratkus/qaradar
```

**Step 2 — install:**

```
/plugin install qaradar@qaradar-marketplace
```

**What you get:** 6 MCP tools auto-configured + 5 slash commands:

| Command | What it does |
|---------|-------------|
| `/qaradar:qa-check` | Full health report — risk, coverage, untested files |
| `/qaradar:qa-risky` | Ranked list of riskiest files with reasons |
| `/qaradar:qa-untested` | Source files with no detected tests + scaffold suggestions |
| `/qaradar:qa-plan` | Prioritized test plan (chains 3 tools) |
| `/qaradar:qa-pr-risk` | Which changed files in this PR are riskiest |

**Example:** after merging a big feature branch, run `/qaradar:qa-check` to see what regressed. Before opening a PR, run `/qaradar:qa-pr-risk` to see what you need to test first.

## MCP Server (for AI Coding Agents)

### Setup

**Alternative: manual MCP config** (if you prefer not to use the plugin):

Add to your Claude Code MCP config (`~/.claude/mcp.json` for user-level, or `.mcp.json` in the project root for project-level):

```json
{
  "mcpServers": {
    "qaradar": {
      "command": "uvx",
      "args": ["qaradar", "serve"]
    }
  }
}
```

Or start it manually:

```bash
uvx qaradar serve
```

### Example Prompts

Once connected, ask your agent:

> "What should I test first in this repo?"
> "Which files are the riskiest right now?"
> "Show me the highest-churn files from the last month."
> "Which source files have no tests at all?"
> "Which of my changed files are risky?" ← diff-aware

### Available MCP Tools

| Tool | When the Agent Uses It |
|------|------------------------|
| `qaradar_healthcheck` | Full quality overview of a repository |
| `qaradar_risky_modules` | What to test first; which files are riskiest |
| `qaradar_churn` | Hotspot detection; where regressions tend to occur |
| `qaradar_coverage_gaps` | Files with low coverage; where the blind spots are |
| `qaradar_untested_files` | Source files with no corresponding test files |
| `qaradar_pr_risk` | Which changed files in this PR need attention |

### Diff-aware: what's risky in this PR?

`qaradar_pr_risk` scores only the files changed between a base ref and HEAD — not the whole repo. It keeps risk scores calibrated by using full-repo normalization, so a file with 2 commits in a PR isn't falsely flagged CRITICAL just because it's the only changed file the agent knows about.

Ask your agent:
> "Which of my changed files are risky?"
> "Do any of the files I changed lack tests?"
> "What should I review before opening this PR?"

Or from the CLI:

```bash
# Diff against main — shows only changed files
qaradar analyze . --base main

# Diff against a specific ref
qaradar analyze . --base origin/main --days 60
```

`qaradar_pr_risk` auto-detects the base branch from `GITHUB_BASE_REF` (set automatically in GitHub Actions) or falls back to `main`/`master`. Pass `base_ref` explicitly to override.

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

# Diff-aware: score only files changed since main
qaradar analyze . --base main
```

## Install

```bash
pip install qaradar
```

Or run without installing:

```bash
uvx qaradar serve
```

**From source** (for development):

```bash
git clone https://github.com/Muratkus/qaradar.git
cd qaradar
pip install -e .
```

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

- [x] **v0.1.2** — Claude Code plugin + slash commands
- [x] **v0.2.0** — Config file (`qaradar.toml`), Tier 2 language validation, hardening
- [x] **v0.3.0** — Diff-aware mode: `qaradar_pr_risk` + `--base` CLI flag
- [ ] **v0.4.0** — Flaky test detection from CI history (JUnit XML parsing)

## Philosophy

QA Radar is built on three beliefs:

1. **The bottleneck has moved.** AI makes writing tests easy. Knowing *which* tests matter is the hard part.
2. **Quality is a landscape, not a number.** A single coverage percentage hides everything. Risk is per-module, per-signal, per-timeframe.
3. **Agents need context.** An AI coding assistant that doesn't know your repo's fragile areas will write generic tests. Give it the quality landscape and it writes targeted ones.

## License

MIT

<!-- mcp-name: io.github.MuratKus/qaradar -->
