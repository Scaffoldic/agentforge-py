# Security Policy

We take the security of AgentForge seriously. Thank you for helping keep the
project and its users safe.

## Supported versions

AgentForge is pre-1.0 and ships on a coordinated release train (all packages
share one version). Security fixes land on the **latest released minor**;
please upgrade to the most recent release before reporting.

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub
issues, discussions, or pull requests.**

Instead, use **GitHub's private vulnerability reporting**:

1. Go to the repository's **Security** tab →
   **Report a vulnerability** (Privately report a vulnerability).
2. This opens a private security advisory visible only to you and the
   maintainers.

> If you cannot use private advisories, you may instead contact the
> maintainer privately. _(Maintainer: add a security contact email here if
> you want a non-GitHub channel — otherwise GitHub private advisories are the
> sole channel.)_

### What to include

- A description of the vulnerability and its impact.
- Steps to reproduce (a minimal proof-of-concept is ideal).
- Affected version(s) and environment (Python version, OS, relevant
  module packages).
- Any suggested remediation, if you have one.

### What to expect

- **Acknowledgement within 72 hours.**
- An initial assessment and severity triage shortly after.
- Coordinated disclosure: we'll work with you on a fix and a release, and
  credit you in the advisory unless you prefer to remain anonymous.
- Please give us a reasonable window to release a fix before any public
  disclosure.

## Scope

In scope: the framework code in this repository (`packages/*`, the CLI, the
scaffolding templates) and the published `agentforge-*` distributions.

Out of scope: vulnerabilities in third-party provider SDKs or services
(report those to the respective vendors), and issues that require a
misconfiguration explicitly warned against in the docs (e.g. committing API
keys as plaintext instead of using `${ENV_VAR}` interpolation).

## Good practice for users

- Never commit secrets — AgentForge config uses `${ENV_VAR}` interpolation
  precisely so keys stay out of source.
- Keep `agentforge-py` and its module packages up to date; security fixes
  ship on the latest minor.
- Use the built-in guardrails (PII redaction, prompt-injection defenses) for
  untrusted input.

Thank you for contributing to the security of AgentForge.
