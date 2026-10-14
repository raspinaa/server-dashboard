# Changelog

## 0.3.0

- Global infrastructure landing dashboard and scoped project/VM navigation.
- Shared Persian RTL design system, bundled Vazirmatn font and account menu.
- Server-side inventory sorting, environment grouping and 30/50/100-row pagination.
- Collapsible project/user forms and categorized reports/import history/audit views.
- Signed ZIP upload with bounded validation and constrained host staging/upgrade worker.
- Field-change audit details and searchable, indexed event pagination.

## 0.2.1

- Automatic XLSX preview and defaults for valid new machines; optional per-row decisions.
- Multiple IPs and CIDR parsing, repeated section headers and merged environment/service groups.
- Empty resource values become zero; network addresses can remain empty.
- Multiple addresses in manual editing and XLSX export; visible header logout and manual machine creation.

## 0.2.0 — Unreleased

- Offline-only application installation and updates from copied signed packages.
- One-command online Debian preparation; bundles include images and hash-locked CLI wheels.
- Local update staging/dashboard metadata, internal backend/database networks and a LAN-facing web bridge and no automatic image pulls.
- Breaking deployment change: GitHub/commit updates and runtime Let’s Encrypt are removed from the supported path. Existing data/keys are preserved; prepare a signed offline bundle for upgrade.

## 0.1.0 — Unreleased

- Scoped management reports, resource graphs, service breakdowns and project-selectable XLSX exports.
- Host CLI for dated full backups, signed release or pinned-commit updates and explicit snapshot restore.

- Remove public demo, its publication workflow and documentation links.



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
