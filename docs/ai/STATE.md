# State

2026-09-29: v0.2.0 removes the three dashboard cards and sidebar navigation. Runtime environment is externalized; repository contains no deployment inventory. Source: docs/REQUIREMENTS.md. Test outcomes are recorded after verification.

Verified: isolated PTY tests pass (10 checks); Python/JS syntax checks pass; Chrome desktop preview inspected and320px viewport has no horizontal overflow. Secret scanner checked reachable history; synthetic token under vendor path is still detected despite two exact false-positive exceptions. Runtime credentials/host settings remain outside Git.

v0.2.1: CI invokes pinned gitleaks8.30.1 against full history directly. This avoids the third-party action's invalid initial-commit-parent range when a tag is pushed. Official release archive checksum is verified before execution.
