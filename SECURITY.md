# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Do not open a public issue for an unpatched vulnerability.

Use GitHub's private vulnerability reporting for this repository:

https://github.com/mastaan66/multi-agent-coding-tool/security/advisories/new

Include:

- affected version and platform;
- reproduction steps or proof of concept;
- expected impact;
- suggested mitigation, if known.

Please allow maintainers reasonable time to investigate before public disclosure.

## Current security boundaries

AI Software Factory processes model-generated content and can execute generated
tests. The current subprocess runner has a timeout but is **not an OS-enforced
sandbox**. Run the tool only in a trusted development environment or an isolated
container.

Generated projects are examples that require normal engineering review, dependency
auditing, secret management, and deployment hardening before production use.

API keys are loaded from the environment or a local .env file. Never commit .env,
paste credentials into issues, or include secrets in demo recordings.
