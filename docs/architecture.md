# Architecture and API

Modular monolith: `models` persistence, `security` scope/crypto/audit, `validation` portable IP/capacity rules, `inventory` versioned transactional edits, `xlsx` bounded mapping/preview/atomic apply/export, `api` session endpoints, `updates` release metadata/queue. Import limit is 10,000 rows / 80 MiB expanded ZIP / 150 columns. Imports are synchronous, bounded, transactional under the project lock; run via Gunicorn with 120-second timeout. Very large datasets beyond these limits need a future bounded background import worker, not unbounded request processing. Update execution already runs outside HTTP through the optional helper.

MySQL 8.4 InnoDB + utf8mb4; identifiers/names use `utf8mb4_0900_as_cs` (case/accent sensitive, Unicode, no implicit unique server-name assumption). Environment/application names are unique within project; machine names and IPs are not. Timestamps use timezone-aware UTC storage, UI uses Persian date display in Asia/Tehran. Portable CharFields store validated IPv4/IPv6 and CIDR prefixes. No infrastructure connections or PostgreSQL extensions.

Stable UUID machine and disk IDs survive edits and workbook round trips. Machine optimistic `version` covers credentials as well as inventory edits. History holds immutable snapshots of changed ordinary fields/disks; credentials generate only redacted activities. Archived record relationships remain intact. All inventory FKs use PROTECT; no generic destructive CRUD endpoint exists.

## API

All paths end with `/`. Authenticated session + CSRF for unsafe requests. 400 validation, 403 authorization/session, 404 scope isolation, 409 stale version. Inventory never contains credential plaintext. JSON examples use no real secrets.

| Route | Methods / purpose |
|---|---|
| `/api/session/`, `/api/login/`, `/api/logout/`, `/api/password/` | CSRF cookie/profile, local login/logout/change password |
| `/api/health/` | database-backed readiness (no authentication) |
| `/api/projects/` | GET scoped list, POST admin create |
| `/api/projects/{id}/` | PATCH manager, expected version |
| `/api/projects/{id}/environments/` | POST/PATCH manager; ID/version for edits |
| `/api/projects/{id}/memberships/` | GET manager; POST additionally manage_users |
| `/api/projects/{id}/machines/` | GET paginated 100 rows, search/environment; POST editor |
| `/api/machines/{uuid}/` | GET/PATCH with expected version |
| `/api/machines/{uuid}/activity/` | GET; POST comment/completed_work; PATCH author/manager with version |
| `/api/machines/{uuid}/credential/` | POST action reveal/copy; PUT credential edit with version |
| `/api/projects/{id}/overview/` | whole-project + selected totals + environment distributions |
| `/api/projects/{id}/imports/` | GET history; POST multipart file |
| `/api/imports/{uuid}/` | GET sanitized preview; POST preview/apply |
| `/api/projects/{id}/exports/` | POST kind inventory/activity, environment, merged, credentials; stream XLSX/no cache |
| `/api/users/` | GET/POST/PATCH manage_users; last-admin guard |
| `/api/settings/` | GET/PATCH auth_settings; bounded session policy |
| `/api/audit/` | read-only global audit permission |
| `/api/updates/` | GET persistent runs; POST check/install/retry with perform_updates |

Preview body: `{"action":"preview","worksheet":"Inventory","header_row":1,"mapping":{"2":"environment","14":"server_name","7":"disk"},"mode":"add_update","version":1}`. Apply requires preview version and decision per nonblank row: `{"action":"apply","version":2,"decisions":{"2":{"action":"apply","match":"candidate-UUID-or-new","fields":"excel","disks":"merge","credential":"preserve"}}}`. Per-field decisions may replace `fields` with an object mapping every incoming ordinary field to `excel` or `web`. `disks` is preserve/merge/replace. No deletion of absent machines occurs. Candidate snapshots and versions are server-held, never accepted from caller.

Uploads are private encrypted storage without public media serving. Filename is metadata only; generated UUID storage names prevent traversal. Ordinary exports are generated on demand and not retrievable later. Export record is metadata only. Formula cells are rejected on import; text exports get formula escaping.

## Toolchain verification (2026-10-12)

Upstream Django stable/5.2.x release notes confirm LTS with at least three years of security support from April 2025 and Python 3.12 support. Upstream DRF README supports Django 5.2. PyPI resolves Django 5.2.18 and DRF 3.18.3. Node 24 satisfies Vite 8.3.4's supported engine range. MySQL official site was blocked by policy; the official Docker MySQL 8.4 LTS image resolves and reports 8.4.11, and integration tests verify engine/strict mode. References: https://raw.githubusercontent.com/django/django/stable/5.2.x/docs/releases/5.2.txt ; https://raw.githubusercontent.com/encode/django-rest-framework/master/README.md ; https://dev.mysql.com/doc/refman/8.4/en/ .

Python dependencies are exactly pinned with PyPI hashes in requirements.lock, npm dependencies in package-lock.json with integrity fields. Python/Node/Nginx/Caddy images are pinned to registry manifest digests resolved on 2026-10-12. MySQL is pinned to the tested 8.4.11 patch. Future releases must refresh reviewed digests with security patch updates. Only Linux amd64 is claimed; arm64 is unverified and refused by installer. Security patch upgrades must regenerate locks, run MySQL and UI tests, and update CHANGELOG before a future signed release.

Corporate egress proxies may require a trusted public CA in isolated Docker builds. Dockerfiles accept an optional BuildKit secret named `enterprise_ca`; supply the organization's approved CA bundle with `--secret id=enterprise_ca,src=/secure/public-ca-bundle.crt`. Apt/TLS and npm integrity verification remain enabled. Do not include private keys. Container runtime production connections need their own reviewed trust configuration; the build certificate does not authorize arbitrary hosts.

ImportValidation and ImportDecision are explicit relational records linked to batch, preview version, row, actor and resulting machine. Preview JSON is a convenient snapshot; normalized results/decisions retain a durable history when a preview is regenerated.
