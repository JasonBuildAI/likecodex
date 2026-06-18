# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security issue, please **do not** open a public GitHub issue.

Instead, report it privately to the maintainers via GitHub Security Advisories or by contacting the repository owner.

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to acknowledge reports within 72 hours.

## Security Model

LikeCodex executes LLM-driven tools on your machine. Important controls:

- **Approval modes**: `read-only`, `auto`, `full-access`, `sandbox-required`
- **Path confinement**: file tools restrict access to the working directory
- **Sandbox execution**: high-risk shell commands can run in Docker
- **API token**: optional Bearer token for `/execute` endpoint

Always run LikeCodex in trusted environments and review permission prompts carefully.
