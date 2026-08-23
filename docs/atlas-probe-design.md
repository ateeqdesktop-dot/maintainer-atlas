# Atlas Probe — Product and Architecture Design

## Product vision

**Atlas Probe** is a local-first, evidence-backed readiness auditor for open-source repositories. It answers a question that security scores and static linters do not answer on their own: *Can an independent contributor reproduce the documented setup, install the project, run the quality gates, and verify the result without trusting a hosted service?*

The product extends the existing Maintainer Atlas passive auditor rather than replacing it. The passive layer remains safe-by-default and never executes repository code. The probe layer is explicit opt-in, bounded, isolated as far as the host permits, and records every command, input, environment fact, duration, exit code, and output digest in a deterministic evidence bundle.

## Problem and target users

Maintainers need more than a popularity or security score. A repository can contain a README, CI workflow, and test directory while its documented quickstart is stale or its clean checkout cannot install. Contributors need a fast answer before investing time. Security reviewers need a reviewable record of what was executed and what was not.

The primary users are open-source maintainers, release engineers, platform teams auditing internal repositories, and contributors evaluating a project. The first workflow is a local CLI run; the second is a GitHub Action that publishes JSON, Markdown, and SARIF artifacts without uploading source.

## Product boundary

Atlas Probe does not become a hosted dashboard, vulnerability scanner, workflow security analyzer, or general-purpose CI runner. It composes with OpenSSF Scorecard, zizmor, actionlint, GitHub artifact attestations, and existing test runners. It focuses on repository readiness evidence and contributor journey reproducibility.

## MVP

| Capability | MVP behavior |
|---|---|
| Passive audit | Preserve all existing Maintainer Atlas rules and output contracts. |
| Probe plan | Read a checked-in `.atlas-probe.toml` or use a conservative ecosystem default. |
| Bounded execution | Run only declared commands with timeout, output-size, process-count, and working-directory limits. |
| Dry run | Show the exact planned commands without executing them. |
| Evidence bundle | Emit deterministic JSON containing plan digest, repository snapshot digest, environment facts, step results, stdout/stderr digests, and verdict. |
| Formats | JSON, Markdown, SARIF for passive findings; Markdown and JSON for probe results. |
| CI action | Add a pinned-action example and upload evidence as an artifact; no network access is required by the core. |
| Privacy | Never include raw stdout/stderr by default; store digests and bounded redacted excerpts only when explicitly requested. |
| Compatibility | Python >=3.10, standard library core, no service dependency. |

## Advanced features

Signed evidence bundles using a user-provided signing command or Sigstore integration; ecosystem-specific adapters for Python, Node, Rust, and Go; contributor-journey probes derived from README commands; GitHub Checks annotations; baseline comparison with added/resolved execution regressions; containerized execution profiles; and a policy registry maintained as versioned rule packs.

## Architecture

```text
                +-------------------------+
                | CLI / GitHub Action     |
                +------------+------------+
                             |
          +------------------+------------------+
          |                                     |
+---------v---------+                  +--------v---------+
| Passive Auditor  |                  | Probe Planner    |
| snapshot + rules |                  | config + policy  |
+---------+---------+                  +--------+---------+
          |                                     |
          +------------------+------------------+
                             |
                    +--------v---------+
                    | Execution Engine |
                    | limits + runner  |
                    +--------+---------+
                             |
                    +--------v---------+
                    | Evidence Writer |
                    | canonical JSON  |
                    +--------+---------+
                             |
       +---------------------+---------------------+
       |                     |                     |
+------v------+       +------v------+       +------v------+
| JSON/MD     |       | SARIF       |       | CI artifact  |
+-------------+       +-------------+       +-------------+
```

The core modules will be separated by stable contracts: `config.py` parses and validates a small TOML schema; `probe.py` owns planning and execution; `evidence.py` owns canonical serialization and hashes; `core.py` remains the passive auditor; and `cli.py` composes commands and exit codes. The executor receives a validated `ProbeStep`, never arbitrary shell text from an internal code path, and invokes commands without `shell=True`.

## Configuration

The initial configuration is intentionally small:

```toml
version = 1
profile = "python"
timeout_seconds = 120
max_output_bytes = 65536
network = "deny"

[[steps]]
id = "install"
command = ["python", "-m", "pip", "install", "-e", "."]

[[steps]]
id = "tests"
command = ["python", "-m", "pytest", "-q"]
```

Only array-form commands are accepted. Environment variables are allowlisted, the working directory is fixed to the repository root, and steps are executed in declaration order. A step may be marked `optional = true`; optional failure produces `review` rather than `block`.

## Data flow and error flow

The CLI resolves the repository path, loads the passive snapshot, parses configuration, validates limits, and constructs a plan digest before any command runs. In dry-run mode it stops there. In execution mode each step receives a monotonic start time, is launched with a timeout, captures bounded output, and is terminated on timeout. The writer records a normalized result, including `spawn_error`, `timeout`, `nonzero_exit`, or `passed`. A malformed configuration, unsafe command, invalid limit, or missing repository is a configuration error with exit code 2. A probe regression is a product verdict with exit code 1 for review or 2 for block, matching the existing audit semantics.

## Security model

Repository content is untrusted data. The passive auditor never executes it. Probes are opt-in and clearly labeled as execution. The engine rejects shell metacharacter-bearing shell commands by not using a shell at all, prevents path escape through a fixed cwd, caps command count, timeout, output, and environment size, and supports `network = "deny"` as a policy signal. Because a normal Python process cannot reliably enforce OS-level network isolation or process isolation on every host, the MVP reports the limitation and provides a container profile as an advanced feature rather than making a false security promise.

Raw output is excluded from canonical evidence by default. Hashes use SHA-256 over UTF-8 bytes. Canonical JSON uses sorted keys and stable separators so the same plan and result produce the same digest except for explicitly volatile fields, which are represented as normalized booleans or durations rounded to milliseconds.

## Observability and performance

The CLI emits concise human-readable progress to stderr and structured evidence to stdout or a file. No telemetry leaves the machine. Repository walking remains bounded by the existing 5,000-file and 256 KB text limits. Probes are sequential in the MVP to preserve determinism and avoid resource contention; future profiles may declare independent steps for safe parallel execution.

## Testing strategy

Unit tests cover TOML validation, command safety, plan hashing, output truncation, timeout normalization, canonical evidence, and policy verdicts. Integration fixtures cover a passing Python repository, a failing test command, an optional failure, malformed configuration, and a timeout. CLI tests verify exit codes and JSON/Markdown output. CI runs formatting-independent tests on Python 3.10–3.13 and executes a safe fixture probe.

## Roadmap

MVP first establishes a trustworthy local contract. The next release adds README-derived contributor journey suggestions, ecosystem adapters, baseline regression diffs, GitHub Checks annotations, and signed bundles. Later releases can add isolated container execution, a public rule-pack registry, and integrations with artifact attestations without turning Atlas Probe into a hosted platform.
