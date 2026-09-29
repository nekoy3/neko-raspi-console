# Security and publication rules

This repository contains reusable source only. All credentials, salts/password hashes, initial password files, TLS keys/certificates, logs, real device responses, host/IP inventories and adapter serial numbers belong outside Git. Runtime data uses data/ (ignored), configurable with CONSOLE_DATA_DIR. Keep the directory700 and secrets600. Do not add broad secret-scanner allowlists. CI scans all Git history with gitleaks; branch protection must be managed separately.

Single-account administration only. No per-user RBAC, automatic device logout, BREAK, power operation, transcript retention or Internet exposure. Receive-only is an input lock, not an authorization boundary against a user who can enable writing.

CSP permits secure WebSockets; the server independently enforces exact Origin/Host and source-network policy. Do not use a public reverse proxy that conceals remote client addresses.
