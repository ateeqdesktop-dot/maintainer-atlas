# Architecture

## Product boundary

Maintainer Atlas has two explicit execution modes. `audit` is passive: it walks a bounded local repository, reads text as untrusted data, applies pure rules, and emits evidence-backed findings. `probe` is opt-in: it executes a reviewed array-form command plan with `shell=False`, a fixed working directory, bounded time and output, and a deterministic evidence record. The passive core never calls the probe engine.

## System shape

```text
local repository
      |
      +---------------------------+
      |                           |
      v                           v
bounded snapshot loader      TOML probe config
      |                           |
      v                           v
pure rule registry           validated probe plan
      |                           |
      +-------------+-------------+
                    |
                    v
             JSON / Markdown / SARIF
                    |
             GitHub Action artifacts
```

The package is intentionally dependency-light. `core.py` contains immutable passive domain types, the bounded loader, pure rules, policy evaluation, and snapshot diffs. `probe_config.py` parses and validates versioned TOML plans. `probe.py` executes the plan and computes stable output digests. `cli.py` owns filesystem boundaries, rendering, and exit codes.

## Passive audit data model

A `RepositorySnapshot` contains a root path, bounded file inventory, detected ecosystems, file sizes, and a digest. A `Finding` contains a stable rule ID, title, category, severity, remediation, repository-relative evidence, and a fingerprint. A `Report` contains the tool version, snapshot digest, findings, diagnostics, and verdict. Evidence references never include source snippets by default.

## Probe data model

A `ProbeConfig` contains a schema version, profile name, global timeout, output limit, network policy signal, and ordered `ProbeStep` values. A step has a unique ID, an argv array, an optional flag, and an optional timeout. `ProbeReport` contains the configuration digest, repository path, network policy, verdict, normalized step results, diagnostics, and an evidence digest.

The evidence digest excludes volatile duration and preview fields. It is computed over canonical JSON with sorted keys and stable separators. Step results retain durations for human diagnostics and output byte counts and SHA-256 digests for reproducibility comparisons. Raw output is omitted by default.

## Security model

All repository content is untrusted. The passive loader never executes scripts, YAML, hooks, package managers, or workflow commands. It skips symlinks and generated directories, caps the file count and text size, and rejects paths outside the repository root.

Probe commands are explicit argv arrays and are invoked with `shell=False`, `stdin=DEVNULL`, a fixed `cwd`, an allowlisted `PATH` and `HOME`, sequential execution, bounded command count, bounded timeout, and bounded captured output. The MVP does not claim kernel-level isolation or reliable network denial for a normal host process. The `network` field is therefore a policy signal and a guardrail for future execution profiles, not a sandbox guarantee.

## Error flow

Invalid paths, malformed TOML, unsupported schema versions, invalid limits, duplicate step IDs, empty commands, and NUL bytes are configuration errors and return exit code 2. A process timeout, spawn error, or non-zero exit becomes a normalized step status. Required-step failure yields `block`; optional-step failure yields `review`; all required steps passing yields `pass`. Diagnostics such as output truncation are retained without exposing raw output.

## Extensibility

New passive rules must remain pure functions over `RepositorySnapshot`. New probe profiles should generate or validate configuration, not bypass the plan contract. Future container execution, signing, GitHub Checks, and ecosystem adapters belong behind explicit interfaces and must not weaken local-first operation or silently convert passive audit into code execution.

## CI contract

The composite action runs the passive SARIF audit by default. If `probe-config` is supplied, it runs the reviewed plan and writes `atlas-probe.json`. The repository CI self-tests both paths and uploads the two evidence files. All third-party action references in the checked-in workflow and action definition are pinned to immutable SHAs except the documented artifact upload reference, which should be pinned before a production release.
