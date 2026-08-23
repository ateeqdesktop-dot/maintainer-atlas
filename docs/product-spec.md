# Product specification

## Vision

Maintainer Atlas makes Open Source readiness inspectable. **Atlas Probe** extends that vision from passive repository contracts to an explicit contributor-readiness proof: a maintainer can show not only that installation and test instructions exist, but that a reviewed command path actually ran and what it produced.

## Users and use cases

The primary user is an open-source maintainer reducing contributor friction. Secondary users are release engineers, platform teams, repository reviewers, and contributors deciding whether a project is practical to adopt.

The core use cases are passive auditing, SARIF generation, baseline comparison, dry-running a probe plan, running reviewed install/test commands locally, and publishing machine-readable evidence as a GitHub Actions artifact without sending source to a hosted service.

## Product boundary

`audit` remains passive and safe-by-default. It reads bounded files and never executes repository code, installs dependencies, follows links, or uploads source. `probe` is an opt-in execution mode, intentionally separate from passive audit. It executes only array-form commands from a versioned TOML plan with `shell=False`, a fixed working directory, bounded timeout, bounded output, and explicit diagnostics about the absence of kernel-level sandboxing in the MVP.

Atlas is not a vulnerability scanner, popularity ranking, observability dashboard, general CI runner, or hosted SaaS product. It composes with Scorecard, zizmor, actionlint, and artifact attestations rather than replacing them.

## MVP acceptance criteria

A fresh checkout can install the package and run the passive audit. The healthy fixture passes and the incomplete fixture produces stable fingerprints. A checked-in probe plan can run the project tests, a dry run performs no execution, required failure blocks, optional failure reviews, timeout becomes a normalized status, and canonical evidence digests remain stable across repeated runs. JSON and Markdown probe reports include no raw output by default. CI exercises both audit and self-probe paths and uploads SARIF and JSON artifacts.

## Domain model

Passive `RepositorySnapshot`, `Finding`, `Policy`, and `Report` types remain immutable and deterministic. Probe `ProbeConfig` contains a schema version, profile, limits, network policy signal, and ordered `ProbeStep` values. `ProbeStepResult` records command identity, normalized status, exit code, duration, output sizes, output digests, optional bounded previews, and optionality. `ProbeReport` records plan identity, verdict, diagnostics, and an evidence digest.

## Verdict semantics

| Condition | Verdict | CLI exit |
|---|---|---:|
| All required steps pass | `pass` | 0 |
| Optional step fails or review diagnostic exists | `review` | 1 |
| Required step fails, times out, or cannot spawn | `block` | 2 |
| Invalid path or configuration | error | 2 |

## Security and privacy requirements

Repository content is untrusted data. Passive rules are pure functions and are isolated from process execution. Probe commands are validated as non-empty argv arrays without NUL bytes, executed sequentially with `stdin=DEVNULL`, a constrained environment, output caps, timeouts, and no shell. Raw output is excluded from evidence by default. The system must never claim that `network = "deny"` provides OS-level network isolation in the normal process runner.

## Roadmap

The next releases may add README-derived journey suggestions, ecosystem-specific profiles, probe baseline diffs, GitHub Checks annotations, signed bundles, and a containerized execution profile. A public rule-pack registry and artifact-attestation integrations remain future work. Local-first operation is a permanent product constraint.
