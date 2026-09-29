# Requirements

## Version 0.2.0 — simplified console layout

Single-purpose screen: header with host name/logout, port list at left, terminal and connection controls at right. Stack on narrow screens. No sidebar navigation or dashboard summary cards.

- Detected port count appears in the port-list heading.
- Exclusive-access state appears on each port, not as a global policy card.
- Receive-only/write-enabled state appears beside the terminal, not as a static safety card.
- Preserve login, HTTPS, server-side input enforcement, explicit writing/paste confirmation, baud selection, per-port lock, RX/TX, disconnect and screen clear.
- No server-management page, multi-user/RBAC, transcripts, BREAK or power control in this version.

Serial tests use PTYs and never touch attached equipment. Browser preview uses fictional output only. Browser trust and actual equipment verification are deployment-side checks, not public artifacts.
