# Maintainer Atlas — Architecture and Product Specification

## Product vision

Maintainer Atlas makes Open Source release readiness inspectable. A maintainer runs one command or adds one GitHub Action, receives findings grounded in repository evidence, and can compare readiness snapshots over time without uploading source code or trusting an opaque score.

## Users and use cases

The primary user is an Open Source maintainer preparing a release or trying to reduce contributor friction. Secondary users are repository reviewers, platform teams defining organization-wide repository policies, and contributors deciding whether a project is safe and practical to adopt.

The core use cases are: audit a local repository; audit a GitHub repository archive; fail CI only for explicitly configured severities; emit SARIF for GitHub code scanning; generate a human-readable remediation report; create a baseline snapshot; compare a candidate snapshot with the baseline; and customize rules or waivers through a policy file.

## Product boundaries

Maintainer Atlas is a passive analyzer in the MVP. It reads bounded repository files and Git metadata, never executes repository code, never installs dependencies, never follows remote links, and never uploads source. It is not a vulnerability scanner, popularity ranking, hosted dashboard, code formatter, or build system. A future sandboxed verification mode must remain opt-in and isolated from the passive core.

## Architecture

```text
repository path / GitHub archive
              |
              v
      bounded source loader
              |
              v
  normalized repository snapshot
              |
      +-------+--------+
      |                |
      v                v
 rule registry     snapshot/diff engine
      |                |
      v                v
 evidence findings   deterministic delta
      \                /
       +------v-------+
              |
       report renderers
 JSON | Markdown | SARIF | exit code
```

The implementation is a dependency-light Python package with four layers. `atlas.model` contains immutable domain types and serialization. `atlas.inspect` loads and normalizes only permitted repository metadata. `atlas.rules` contains pure rule functions receiving a snapshot and returning evidence-backed findings. `atlas.reporting` renders stable JSON, Markdown, and SARIF. `atlas.cli` handles arguments, policy loading, exit semantics, and filesystem boundaries.

## Domain model

A `RepositorySnapshot` contains repository identity, detected ecosystems, bounded file inventory, normalized GitHub-like metadata when available, workflow metadata, and a digest. A `Finding` contains a stable rule ID, title, severity (`info`, `warning`, `error`, `critical`), category, message, remediation, evidence references, and deterministic fingerprint. A `Policy` contains enabled rules, severity overrides, ignored rules, waivers with expiry, and threshold behavior. A `Report` contains the snapshot digest, findings, counts, verdict, and tool version.

Evidence references use repository-relative paths and optional line ranges. Content snippets are not emitted by default to avoid leaking secrets. Files are read with byte and line limits. Symlinks, hidden directories outside the repository root, binary files, and unsupported encodings are skipped safely.

## Built-in rule packs

The MVP ships with rules covering `license.present`, `readme.present`, `contributing.present`, `security.policy_present`, `community.code_of_conduct`, `community.issue_templates`, `community.pull_request_template`, `ownership.codeowners_present`, `ci.workflow_present`, `ci.workflow_pinned_actions`, `tests.detected`, `package.metadata_present`, `release.changelog_present`, `release.version_source`, `docs.quickstart_present`, and `repo.no_large_tracked_artifacts`.

Rules are intentionally evidence-backed rather than score-based. The default verdict is `pass` when no error/critical findings exist, `review` when warnings exist, and `block` when errors/critical findings exist. Users may configure a threshold.

## Error and security model

Malformed policy, unreadable repository paths, traversal attempts, invalid UTF-8, oversized files, and malformed SARIF inputs fail closed with actionable CLI errors. Rule failures are isolated: one malformed optional artifact becomes a finding or diagnostic and cannot crash the full audit. The analyzer treats all repository content as untrusted data; it does not execute YAML, shell, Python, package scripts, hooks, or workflow commands. GitHub archive input is fetched only in a future explicit adapter; the MVP accepts local paths to preserve a zero-network guarantee.

## Performance and extensibility

The loader performs one bounded directory walk and caches normalized file metadata. Rules are pure and independently testable. New rule packs register through a stable `Rule` protocol; no dynamic imports or plugin execution occur in the MVP. Reports are deterministic across runs, enabling content-addressed snapshots and meaningful diffs. The future extension point is a versioned policy/rule-pack API, not arbitrary executable plugins.

## CI/CD contract

The GitHub Action runs `python -m maintainer_atlas audit . --format sarif --output maintainer-atlas.sarif`, uploads SARIF, and optionally writes a Markdown summary. Exit code 0 means pass, 1 means review, 2 means block or invalid input. The action is pinned to a release tag in examples and can be invoked without secrets.

## MVP acceptance criteria

A fresh checkout can run an audit with the standard library only. The included healthy fixture passes. The incomplete fixture produces stable findings with valid evidence paths. A hostile fixture containing symlinks, binary files, huge files, malformed YAML-like text, and executable-looking scripts is never executed and is handled deterministically. JSON, Markdown, and SARIF outputs validate. Snapshot diff identifies added, removed, and resolved fingerprints. Tests cover rules, policy, loader safety, renderers, CLI exit codes, and determinism. CI runs lint-free tests on supported Python versions.

## Roadmap

The next release can add a GitHub metadata adapter, ecosystem-aware package rules, policy-pack publishing, signed snapshots, contributor journey checks, reproducibility probes inside a disposable sandbox, and GitHub Checks annotations. A hosted service is explicitly out of scope until local-first adoption proves demand.
