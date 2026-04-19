# Changelog

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
