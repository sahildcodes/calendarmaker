# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability. Use
GitHub's **Report a vulnerability** option under the repository's Security tab
so the report and any proof of concept remain private.

Include the affected endpoint or component, reproduction steps, potential
impact, and any suggested mitigation. Reports will be acknowledged as soon as
practical.

## Secrets and personal data

Never commit Google OAuth credentials, tokens, populated `.env` files, calendar
exports, or user-uploaded images. The repository's ignore rules exclude the
known runtime credential and token locations. Use synthetic data for issues,
tests, and demonstrations.

If a secret is accidentally committed, revoke it at its provider immediately.
Removing it from the latest commit is not sufficient because it remains in Git
history.
