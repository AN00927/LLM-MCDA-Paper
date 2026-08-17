# Security Policy

## Reporting Security Issues or Accidental Secret Exposures

We take security and privacy seriously, particularly regarding API keys, credentials, and benchmark integrity.

If you discover a security vulnerability, an accidental credential leak, or a security issue with this repository:

1. **Do NOT open a public GitHub issue.**
2. Please report the issue privately by emailing the repository maintainer:
   - **Ahaan Nigam**: [ishaannigam27@gmail.com](mailto:ishaannigam27@gmail.com)
3. Include details of the vulnerability or exposed secret, including steps to reproduce or commit hashes if applicable.

We will acknowledge receipt of your report within 48 hours and work on remediation promptly.

## Secrets and API Keys

- Never commit `.env` files or hardcode API keys (OpenRouter, OpenAI, Anthropic, etc.).
- Always use environment variables or `.env` files (which are ignored by `.gitignore`).
- If an API key is accidentally exposed in a commit, rotate and revoke the key immediately in your provider dashboard.
