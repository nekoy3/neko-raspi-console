# Project guidance

Read docs/ai/INDEX.md, then only relevant linked files.
- Never commit credentials, key material, deployment settings, logs, internal inventory, or real device output.
- Default every serial session to read-only; retain server-side enforcement and exclusive port locks.
- Never send real console input without explicit authorization. verify_pty.py uses an isolated temporary directory and pseudoterminal.
- Test: python verify_pty.py; syntax: python -m py_compile server.py initialize.py; node --check static/app.js.
- Keep project memory concise and free of deployment specifics.
