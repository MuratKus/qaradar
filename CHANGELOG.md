# Changelog

## 0.4.0 (2026-06-05)

### Features

- **Mobile + monorepo language coverage.** Language definitions are now consolidated into a single registry (`qaradar/analyzers/languages.py`) — previously the source-extension list was duplicated and drifting between `test_mapping.py` and `churn.py`. On top of that:
  - **Objective-C** (`.m`/`.mm`, XCTest `FooTests.m`) and **Dart/Flutter** (`.dart`, `foo_test.dart`, `coverage/lcov.info`) are now supported.
  - **Swift** and **Kotlin** are promoted to first-class with real test-function counting (`func test…`, `@Test`).
  - **React Native** dash-suffix test convention (`Foo-test.ts`) is recognized.
  - **Jest/Istanbul coverage** (`coverage-final.json`, `coverage-summary.json`) is parsed, with monorepo auto-discovery under `packages/*/coverage` and `apps/*/coverage` and repo-relative path normalization.
- **Run persistence + re-run criteria (opt-in).** `qaradar analyze --save` records a snapshot (last commit, timestamp, per-file risk) to `.qaradar/state.json`. New `qaradar should-run` evaluates whether a re-run is warranted — exit 0/1 plus a JSON decision with recommended scope (`full`/`diff`) — so it can gate cron/CI/git-hooks. `qaradar status` shows the last run and current decision, and `--save` reports a risk delta vs the previous run. Cadence is configured via a new `[schedule]` table (`interval_days`, `min_changed_files`) in `qaradar.toml`.
- **New MCP tool `qaradar_should_run`** — lets an agent check, after finishing work, whether QA Radar should re-analyze and over which scope.

## 0.3.3 (2026-04-20)

### Bug fixes

- **MCP event-loop blocking** — all six async tool handlers in `server.py` now offload their blocking engine work via `anyio.to_thread.run_sync()`. Previously, sync functions like `run_pr_risk()` and `analyze_churn()` were called directly inside async handlers, which stalls Windows's ProactorEventLoop (IOCP) indefinitely — causing the 1h+ hang observed against `browser-use`. The v0.3.2 `stdin=DEVNULL` fix addressed a different symptom (stdin inheritance) but not this root cause.

## 0.3.2 (2026-04-20)

### Bug fixes

- **MCP Windows subprocess hang** — `_git()` now passes `stdin=subprocess.DEVNULL` to all git subprocesses. Without this, git inherits the MCP server's stdin pipe (connected to the MCP client) on Windows and can block indefinitely. Discovered during OSS validation: `qaradar_pr_risk` hung for 6+ minutes against `browser-use`. Same root-cause class as the cp1252 encoding bug in v0.3.1.
- **`--json-output` missing file-level data** — `qaradar analyze --base <ref> --json-output` now returns the full ranked file list (`risky_changed_files`, `changed_files_without_tests`, `changed_test_files`, `changed_untracked_by_analyzers`) in addition to aggregate counts. Previously only returned summary counts, making the JSON output useless for programmatic/agent consumption. Adds `PrRiskReport.to_dict()` as the canonical serialization method.

## 0.3.1 (2026-04-20)

### Bug fixes

- **Windows encoding crash** — `_git()` now uses `encoding="utf-8", errors="replace"` instead of the system default (cp1252 on Windows). Repos with emoji or non-ASCII characters in commit messages or author names no longer crash `analyze_churn`. Discovered during OSS validation against `browser-use`.
- **Duplicate risk entries on Windows** — `TestMapping.source_path` is now stored as a POSIX path (`source.as_posix()`). Previously, Windows backslash paths from test_mapping and forward-slash paths from git churn were treated as different files in `score_risks`, producing duplicate entries and inflated risk counts in PR reports.
- **Null guard in churn analyzer** — `analyze_churn` now handles a `None` return from `_git()` gracefully instead of raising `AttributeError`.
- **Sample directories excluded by default** — `examples`, `cookbook`, `cookbooks`, `samples`, `demo`, `demos` are now in `SKIP_DIRS` and excluded from source file discovery without needing a `qaradar.toml`. Fixes inflated untested counts on repos like `agno` (1928 → 462 untested after excluding `cookbook/`).

## 0.3.0 (2026-04-20)

### Features

- **Diff-aware mode** — new `qaradar_pr_risk` MCP tool and `qaradar analyze --base <ref>` CLI flag score only files changed between a base ref and HEAD. Designed for PR workflows: ask your agent "which of my changed files are risky?" and get a ranked list scoped to the diff.
- **Auto base-ref detection** — resolves base from `GITHUB_BASE_REF` env (set automatically in GitHub Actions), then `origin/HEAD`, `main`, `master`. Pass `--base` explicitly to override.
- **`qaradar/git.py` shared helper** — `_git`, `changed_files`, `resolve_base_ref`, and `fork_point_sha` promoted to a shared module; `churn.py` now imports from there. Internal refactor, no user-visible behavior change.
- **New slash command** — `/qaradar:qa-pr-risk` wraps `qaradar_pr_risk` with a sensible prompt for summarizing PR risk.
- **`PrRiskReport` model** — new dataclass returned by `run_pr_risk`; includes per-bucket counts, changed test files, changed files without tests, and files untracked by analyzers (`.md`, `.yml`, etc.).

### Correctness

- Risk normalization uses full-repo churn even in diff-aware mode. Pre-filtering churn to only changed files would inflate scores; now the filter happens on the output layer, preserving calibrated scores.
- Windows path normalization: `TestMapping.source_path` backslashes are converted to POSIX forward slashes before comparing with `git diff --name-only` output.

## 0.2.0 (2026-04-19)

### Features
- **`qaradar.toml` config file** — optional per-repo config for risk weights, coverage path override, and file excludes. All settings have defaults; no config = existing behavior unchanged.
- **Coverage file auto-discovery** — scans `coverage/coverage.xml`, `coverage/coverage.json` in addition to existing root-level paths. Explicit `[paths].coverage_file` in `qaradar.toml` overrides discovery.
- **Config-driven risk weights** — override churn/coverage/test_mapping weights via `[weights]` section.
- **Config-driven excludes** — skip vendor dirs, generated files, or any glob pattern via `[excludes].patterns`.

### Language improvements (Tier 2 validation)
- **Rust**: Fixed test detection for the standard integration-test pattern (`tests/` directory sibling to `src/`). Previously 0% detection on real Rust repos; now correctly matches crate-level integration tests.
- **Ruby**: Confirmed `spec/*_spec.rb` pattern works correctly on `lostisland/faraday` (24/33 source files detected).
- **Java**: Confirmed `FooTest.java` / `FooTests.java` patterns work on `FasterXML/jackson-core` (37/138 — lower rate reflects structural tests, not a bug).

### Error handling
- Non-git directory now raises `ValueError` with a clear message instead of leaking a raw git error.
- Missing `git` binary detected at entry and reported cleanly via `RuntimeError`.
- No coverage file found: engine sets `coverage_status = "no_report_found"` in the report (instead of silent empty list). Healthcheck JSON includes `coverage_status` field.
- Empty repo (no source files) returns a zero-state report instead of crashing.

### Docs & metadata
- Fixed broken clone URL in README (`murat` → `Muratkus`).
- Removed stale "PyPI release coming in v0.1.2" notice.
- Reordered Install section: `pip install qaradar` / `uvx qaradar serve` is now primary.
- Roadmap pruned: cut exploratory charter generation (v0.5) and historical trend tracking (v1.0); deferred GitHub Action integration; diff-aware mode remains next as v0.3.0.
- Added `Changelog` and `Issues` URLs to `pyproject.toml`.

### Internal
- `qaradar/config.py` — new `QaradarConfig` Pydantic model with `load_config(repo_path)`.
- `tomli` added as a dependency for Python 3.10 compatibility (`tomllib` is stdlib 3.11+).
- Config threaded through engine, all analyzers, MCP server tools, and CLI.
- 91 tests (up from 62 in v0.1.2).

---

## 0.1.2 (2026-04-17)

- Claude Code plugin integration: `/plugin install qaradar@qaradar-marketplace` wires up MCP server + 4 slash commands.
- Slash commands: `/qaradar:qa-check`, `/qaradar:qa-risky`, `/qaradar:qa-untested`, `/qaradar:qa-plan`.
- PyPI release: `pip install qaradar` / `uvx qaradar serve`.
- GitHub Actions CI: lint + types + tests on Python 3.10–3.12.

---

## 0.1.0 (2026-04-14)

- Initial release: MCP server with 5 tools (`qaradar_healthcheck`, `qaradar_risky_modules`, `qaradar_churn`, `qaradar_coverage_gaps`, `qaradar_untested_files`).
- CLI: `qaradar analyze`.
- Tier 1 language support: Python, JavaScript/TypeScript, Go.
- Coverage formats: coverage.py JSON/XML, Cobertura, LCOV, Go cover profile.
- Risk scoring: churn × coverage × test-mapping weighted combination.
