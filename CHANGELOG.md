# Changelog

## 0.1.0 — Unreleased

- Fix Pages workflow: initial enablement requires repository administrator settings, while the standard workflow token publishes an already-enabled site.

- Standalone Persian RTL demo with synthetic inventory, interactive resource summaries and session-only edits; dedicated GitHub Pages publication workflow.

- Explicit, repeatable private-file ownership/modes in both installers; reject unsafe links and preserve database ownership.
- Readable application state, root-only backup/staging storage and private Gunicorn file creation.

- Product-first Persian introduction and staged Debian 12/13 amd64 bootstrap source.
- Pinned source download, explicit ACME/local/HTTP transport, optional isolated local DNS.
- Durable site overrides, idempotent administrator setup and CA/config preservation in backups.

- Persian RTL project/environment inventory with independent disk records and stable UUIDs.
- Local session authentication, scoped memberships, independent credential/export/update permissions.
- Optimistic edits, activity/comments with revisions, field-level and disk history.
- Mapped XLSX preview, merged-cell support, explicit matching/conflict decisions, atomic import, dynamic export.
- Inventory-derived project and environment resource summaries.
- Authenticated credential encryption, timed reveal/copy and redacted auditing.
- Source-only Compose, installer, backup/restore, signed artifact and constrained update tooling.

Source repository: `raspinaa/server-dashboard`. No release tag, container upload or production deployment is implied.
