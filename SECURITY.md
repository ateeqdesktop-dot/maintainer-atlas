# Security Policy

## Scope

Maintainer Atlas handles repository files as untrusted input. Passive audit mode is designed not to execute repository code, import project modules, follow links, install dependencies, or upload source. Probe mode is an explicit execution feature and must be configured by a reviewed plan.

## Supported versions

The latest tagged release receives security fixes. Development snapshots may change evidence schemas and are not recommended for security-sensitive automation.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories. Do not include secrets in public issues. Include the affected version or commit, reproducible steps that do not expose credentials, and the impact observed. We will acknowledge, investigate, and document a fix or mitigation as soon as practical.

## Security boundaries

Probe execution uses `shell=False`, explicit argument arrays, a fixed working directory, bounded command count, bounded time, bounded output, and an allowlisted environment. The MVP does not provide a complete operating-system sandbox or guarantee network isolation. Use a container or a separate disposable environment when the reviewed plan is not trusted.

Atlas emits no telemetry. Raw probe output is excluded from canonical evidence by default; only bounded metadata and digests are recorded.
