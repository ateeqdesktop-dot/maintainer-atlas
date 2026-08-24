# Maintainer Atlas — Product and Architecture

## Product decision

**Maintainer Atlas** will become an open-source, local-first **release decision compiler**. It answers a concrete question that security scorecards and simple checklists do not answer completely: *Can this exact repository state be released, and what reproducible evidence supports that decision?*

The product will not claim to certify security, guarantee sandboxing, or replace human review. It will compile bounded passive evidence and explicitly authorized verification evidence into a deterministic bundle with a verdict, stable findings, baseline comparison, and machine-readable outputs.

## Problem statement

Maintainers often have a repository that appears healthy while its public contract is incomplete: the quickstart may be broken, tests may not be discoverable, release metadata may disagree with package metadata, workflow actions may be mutable, or a release artifact may not be reproducible. Existing tools tend to optimize for one dimension: security posture scoring, dependency scanning, or a static checklist. They rarely connect repository evidence, bounded execution, baseline regressions, and a release-specific decision in one reviewable artifact.

## Target users and use cases

The primary users are solo maintainers preparing a first public release, open-source teams reviewing pull requests, and platform teams enforcing release gates without uploading source. A user should be able to run a passive audit locally, configure a reviewed verification plan, compare the current state with a committed baseline, emit SARIF/JUnit/JSON/Markdown, and use the same command in GitHub Actions.

## MVP scope

The MVP is an evolution of the existing private core. It will retain passive repository scanning and bounded probes, then add a stable evidence schema, explicit baseline semantics, finding status (`new`, `unchanged`, `resolved`), deterministic report IDs, policy configuration, stronger ecosystem checks, and a polished GitHub Action. The CLI remains the primary interface and does not require a service, database, account, or external API.

The MVP will include: repository snapshot hashing; passive rules for governance, documentation, community, CI, package metadata, release metadata, and hygiene; safe probe plans using array-form commands and bounded resources; baseline creation and diff; JSON/Markdown/SARIF outputs; JUnit output for CI; stable exit codes; diagnostics separated from findings; fixture repositories; unit and integration tests; packaging metadata; a security policy; contribution guidance; examples; and GitHub Actions for quality, release, and action smoke tests.

## Advanced roadmap

The next release will add ecosystem adapters for Python, Node, Rust, and Go; package-version consistency checks; GitHub Checks annotations; signed evidence bundles; a rule-pack interface; and an optional container execution profile. Later releases may add release-artifact verification, provenance/attestation ingestion, historical trend snapshots, and a GitHub App. None of these are required for the local-first core to remain valuable.

## Functional requirements

| Requirement | Acceptance criterion |
| --- | --- |
| Passive audit | Never executes repository code, follows symlinks, installs dependencies, or uploads source. |
| Evidence | Every finding has a stable rule ID, severity, remediation, fingerprint, and repository-relative evidence. |
| Verification | Commands are explicit argument arrays, run without a shell, bounded by timeout/output/count, and clearly labeled as execution. |
| Determinism | Same repository state and same plan produce the same snapshot/evidence identity apart from normalized runtime fields. |
| Baselines | A committed baseline can distinguish new, unchanged, and resolved findings without relying on line numbers alone. |
| CI interoperability | JSON, Markdown, SARIF, and JUnit are valid and useful in GitHub Actions and generic CI. |
| Exit contract | `0` pass, `1` review, `2` block or invalid input; contract documented and tested. |
| Privacy | No telemetry and no network dependency in the core workflow. |

## Non-functional requirements

The tool must be installable with `pipx`, `pip`, or a source checkout; support Python 3.10–3.13; remain dependency-light; bound filesystem traversal and text reads; finish passive scans quickly on ordinary repositories; fail closed on malformed configuration; produce actionable diagnostics; and preserve backward compatibility for the current CLI examples.

## Architecture

```text
CLI / GitHub Action
        |
        v
Input + Policy Loader ---- Probe Plan Validator
        |                         |
        v                         v
Repository Snapshot ------ Bounded Execution Engine
        |                         |
        +------------+------------+
                     v
             Evidence Normalizer
                     |
       +-------------+-------------+
       |             |             |
   Verdict       Baseline       Renderers
   Engine        Diff            JSON/MD/SARIF/JUnit
```

The core remains a set of pure or bounded modules. `core.py` owns filesystem snapshots, passive rules, findings, policies, verdicts, and baseline-compatible fingerprints. `probe_config.py` owns TOML parsing and validation. `probe.py` owns explicit execution and normalized results. A new `evidence.py` module will own canonical serialization, bundle identity, and status-aware comparison. `renderers.py` or the existing CLI layer will own output formats and must not mutate the domain model. The CLI composes these modules and translates domain outcomes into the stable exit contract.

## Data flow

The CLI resolves and validates the repository path, loads the policy and optional probe plan, creates a bounded snapshot, executes passive rules, validates the probe plan, optionally executes authorized steps, normalizes all results, computes canonical evidence IDs, applies baseline comparison, evaluates the policy threshold, and renders the requested output. In dry-run mode no command is executed. In passive audit mode no repository code is executed. The report records the mode and its guarantees.

## Error flow

Invalid repository paths, malformed TOML, unsafe command structure, invalid limits, unsupported output formats, and unreadable required inputs are configuration errors with exit code `2`. A timed-out or failed required probe is a blocking/review finding according to policy, not an unhandled exception. A rule failure is recorded as a diagnostic and produces a conservative review/block outcome rather than silently disappearing. Renderer failures are surfaced as process errors without rewriting the evidence model.

## Security model

Repository contents are untrusted data. Passive mode uses bounded traversal, skips symlinks and generated directories, limits text reads, and never evaluates Markdown or configuration code. Probe mode is opt-in and uses `subprocess.Popen` with `shell=False`, a fixed repository working directory, an allowlisted environment, sequential execution, bounded timeout, bounded output, and no implicit network access. The `network = "deny"` setting is a policy signal in the MVP, not a claim of OS-level isolation; containerized isolation is a future profile.

## Observability and performance

The CLI writes concise progress and diagnostics to stderr and structured reports to stdout or a file. Each probe records duration, exit status, output sizes, and digests while excluding raw output by default. Repository traversal is capped. The implementation avoids global state and keeps rule execution independently testable. A future `--verbose` mode may expose timing per rule without changing the evidence identity.

## Test strategy

Tests will cover model invariants, stable fingerprints, snapshot determinism, rule behavior, policy overrides and waivers, malformed plans, command safety, timeout and output limits, baseline status transitions, JSON/SARIF/JUnit schema validity, CLI exit codes, fixture repositories, and GitHub Action smoke execution. The CI matrix will run supported Python versions, lint/type checks where available, packaging validation, and a safe probe fixture.

## Release strategy

The public release will include a polished README with a five-minute quickstart, a threat model, a compatibility matrix, example outputs, contribution guide, code of conduct, security policy, changelog, issue templates, CODEOWNERS, pinned GitHub Actions, build metadata, and a release workflow that validates the package and example action. The first public tag will be `v0.3.0` after the expanded contract is tested.
