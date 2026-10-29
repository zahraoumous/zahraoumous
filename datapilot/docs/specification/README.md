# DataPilot specifications

Updated 2026-10-29 for the implemented local MVP.

Start with [FUNCTIONAL_SPEC.md](FUNCTIONAL_SPEC.md), the current specification for accounts, workspaces, imports, quality, cleaning, analytics, dashboards, skills, provider/model/key settings, languages, themes and exports. It includes acceptance criteria, calculation definitions and explicit limitations.

## Current references

- [Application guide](../../README.md): setup, upgrades and user workflows.
- [Validation report](../VALIDATION.md): checks actually executed and limitations.
- [Security notes](../SECURITY.md): local deployment and credential handling.
- [Generated API contract](../../packages/api-contract/openapi.json): implemented endpoints and declared schemas.
- [Generated TypeScript declarations](../../packages/api-contract/index.d.ts).
- [Database migrations](../../services/api/alembic/versions/): authoritative upgrade sequence.

## Historical design references

`ARCHITECTURE.md`, `CODEX_TASKS.md`, `openapi.yaml` and `schema.sql` retain the original design as historical reference. Their target features and unchecked backlog do not describe current delivery status. Use the functional specification, generated API contract and migrations for the running application.

The implemented release uses local account sessions, deterministic Python computations over canonical Parquet, fixed application-owned AI skills and a portable Power BI handoff. It does not implement the original design's OIDC, DuckDB query compiler, automatic AI query planner, verified-claim narrator or native `.pbit` template.
