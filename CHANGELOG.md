# Changelog

All notable changes to Maintainer Atlas are documented here.

## 0.3.0 — 2026-08-24

### Added

- Canonical evidence bundles with schema version, deterministic evidence identity, and baseline status classification.
- `new`, `unchanged`, and `resolved` finding states for regression-aware review.
- JUnit output for generic CI test-report ingestion.
- Product and architecture documentation covering requirements, data flow, error flow, security boundaries, and roadmap.
- Expanded contributor, security, community, and release documentation.

### Changed

- JSON audit snapshots now represent reusable evidence baselines rather than only raw reports.
- README and GitHub Action examples now use immutable action references and the 0.3.0 contract.

### Compatibility

The existing `audit`, `probe`, and `diff` commands remain available. Exit codes remain `0` for pass, `1` for review, and `2` for block or invalid input.

## 0.2.0

- Add Atlas Probe with versioned TOML plans and explicit dry-run mode.
- Add bounded, shell-free execution with timeout, output caps, optional steps, and normalized verdicts.
- Add canonical JSON evidence bundles with stable configuration, output, and evidence digests.
- Add probe CLI output, Python API exports, self-probe configuration, and GitHub Action integration.
- Expand tests to 13 passing cases covering determinism, timeout, optional failure, validation, and CLI behavior.
- Refresh README, product specification, architecture documentation, and CI artifacts.

## 0.1.0

- Initial local-first evidence-backed repository readiness auditor.
