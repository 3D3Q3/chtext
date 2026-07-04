# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [1.1.0] - 2026-07-04

### Fixed
- Quote-history database is now stored in `~/.chtext/seen_ids.sqlite` instead of the current working directory. Previously, running `chtext` from different directories created separate history files, silently breaking duplicate detection and littering project folders. An existing `seen_ids.sqlite` in the working directory is migrated automatically on first run.
- API client now checks HTTP status codes and wraps network failures, so outages and rate limits surface as clean error messages instead of raw tracebacks.
- Non-JSON API responses (e.g. HTML error pages) now raise a descriptive `CtextAPIError`.
- `Ctrl+C` is no longer swallowed during `chtext browse` chapter listing (bare `except` removed).
- Windows UTF-8 console configuration moved from import time into `main()`, so importing `chtext` as a library no longer replaces `sys.stdout`/`sys.stderr` globally.
- README installation commands were broken (markdown links pasted inside code blocks); now copy-pasteable.

### Added
- Test suite (`tests/`) covering the API client, duplicate-tracking database, segment extraction, and configuration — all network access mocked.
- CI workflow: ruff lint + pytest across Python 3.8–3.13 on every push and pull request.
- This changelog.

### Changed
- Package version is now single-sourced from `chtext.cli.__version__` via `pyproject.toml` dynamic metadata.
- Build system requirement raised to `setuptools>=77` (required by the SPDX `license = "MIT"` expression already in use).
- Code style cleanup (unused imports, redundant f-strings) enforced by ruff.

## [1.0.0] - 2026

Initial public release.
