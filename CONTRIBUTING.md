# Contributing to Maintainer Atlas

Thank you for helping make release readiness inspectable. Maintainer Atlas is intentionally dependency-light and passive, and it treats evidence contracts as public API.

## Local setup

Use Python 3.10 or newer, create a virtual environment, and install the development extra:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Before opening a pull request

Create a focused fixture for every rule change, run `python3 -m pytest -q`, and explain any policy or security impact in the pull request. New rules need a stable rule ID, repository-relative evidence, remediation text, and an explicit false-positive consideration. Changes to fingerprints, JSON schema, exit codes, or probe safety must explain compatibility impact.

Do not add code that executes repository content, follows links, uploads source, adds secrets, introduces absolute paths, or depends on the network in tests. Probe changes must remain explicit, bounded, and free of `shell=True`.

Exercise the CLI when changing output formats:

```bash
python -m pytest -q
maintainer-atlas audit examples/healthy --format json
maintainer-atlas audit examples/incomplete --format markdown
maintainer-atlas probe examples/healthy --dry-run
```

## Pull requests

Explain the user problem, the contract being added or preserved, the evidence that proves the behavior, and any security or privacy trade-off. Documentation and changelog updates are expected for user-visible changes. Maintainer Atlas is local-first, evidence-backed, deterministic where practical, and honest about limitations; contributions should make a release decision easier to review, reproduce, or remediate.
