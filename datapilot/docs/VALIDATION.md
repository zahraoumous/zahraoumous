# Validation evidence — completed local MVP

Validated on **2026-10-28**, with final regression checks repeated on **2026-10-29**, Linux amd64, using the supplied Docker Compose topology. Results below describe checks actually run against the updated source.

## Automated checks

- **81 tests passed, none skipped**, with two distinct fresh disposable PostgreSQL databases. Coverage includes parser/body limits, accounts/sessions/origin checks, workspace membership, upload rollback and paths, immutable cleaning, deterministic numerical results, filtered exports, AI key handling and mocked provider adapters.
- Migration validation first installs the uploaded `0002` schema, creates a local account/password hash, workspace membership and import, and upgrades to `0004_ai_mvp`. The account/password, membership and import remain intact. ORM metadata comparison, tenant foreign keys, downgrade to base and re-upgrade also pass.
- Ruff lint and formatting, mypy over 27 API/worker modules, and TypeScript checks pass.
- Next.js production builds pass inside Docker, including TypeScript checking and static page generation. The host's restricted sandbox initially blocked a Node subprocess; Docker builds run normally without weakening verification.
- OpenAPI and TypeScript API declarations were regenerated from the implemented API. CI now includes both the original import checks and the additional MVP API/browser checks. A GitHub-hosted CI run was not performed here.

## Docker and real HTTP workflows

An isolated Compose project was built and started from the updated source. PostgreSQL, Redis, API and worker reached their configured health checks; MinIO and the web service started. API readiness verified migrated PostgreSQL, Redis and authenticated object storage. Existing validation accounts and imports remained available after repeated container rebuilds. Preexisting Docker projects and volumes were retained.

The following scripts passed:

```sh
python3 scripts/smoke.py
python3 scripts/check-wireframes.py
python3 scripts/real-flow-smoke.py
python3 scripts/mvp-flow-smoke.py
node scripts/browser-smoke.mjs
node scripts/browser-mvp-smoke.mjs
```

The original real-flow check verifies registration/login/logout, real CSV/XLSX uploads, nested source paths, a malformed XLSX isolated from successful files, background worker execution, exact counts/checksums/previews/quality findings, subsequent imports, and cross-account denial.

The additional MVP check verifies cleaning preview and approval into a distinct immutable version; original rows and source hash retention; exact revenue/cost/quantity/profit over the complete selected version; saved analysis and dashboard retrieval; CSV/XLSX/JSON/PDF and Power BI handoff downloads with real data; English/French/Arabic local skill answers; masked provider key save/retain/clear; and cross-account denial for versions, analysis, dashboard and AI access.

## Real Chromium workflows

The original browser check passes account creation, workspace creation, folder selection including nested CSV files, visible unsupported-file exclusion, actual processing, preview/schema, session reload, HttpOnly SameSite session cookie, mobile layout without document overflow, and sign-out/sign-in restoring the workspace.

The MVP browser check passes cleaning operation selection and explicit approval, cleaned-version selection, semantic mappings, exact displayed metrics and charts, saved dashboard and reload, provider/model/key settings and key removal, skill-guided local answer/evidence, five actual downloads, persistent dark theme, French navigation, Arabic RTL, and a 390px Arabic mobile view without horizontal document overflow. No browser page errors were reported. Dark/Arabic screenshots were also inspected for readability.

Screenshots from these real executions are included in `docs/screenshots/`, including `cleaning-review.png`, `dashboard-dark.png`, `skill-answer.png`, `arabic-export-dark.png` and `arabic-mobile.png`.

## Corrections found during verification

Real checks exposed and corrected UUID serialization in analysis JSON exports, missing `PUT` forwarding and `Content-Disposition` headers in the same-origin web proxy, shared integration-fixture setup, and cleaned-version quality flags. A regression test verifies that mixed-type and formula-like warnings persist when the underlying values remain. Final review also corrected dashboard saving to use the analysis displayed in the visible snapshot; a browser regression checks this with two distinct saved analyses. Displayed long decimals are formatted for readability; evidence and exports retain exact calculation values.

## Scope and limits

External OpenAI, Anthropic and Gemini request/response behavior is tested with mocks; no live provider API key was supplied and no live external completion is claimed. Local evidence mode is verified end-to-end without a key. External use requires a valid provider account/model/key and network access to that provider.

The PDF is a fixed English numerical report with visible escapes for non-ASCII text, not a fully localized or Arabic-shaped document. CSV/XLSX/JSON preserve Unicode. The Power BI export is a portable ZIP handoff, not a native `.pbix`/`.pbit` file.

No production deployment, production security certification, dependency/container audit, backup/restore drill, arm64 runtime check, or live database connector/watch-folder test was performed. OIDC/recovery, automatic joins, watched folders and team administration remain later increments. The Starlette/httpx upstream deprecation warning remains; it does not prevent the 81 tests from passing.

The downloadable ZIP contains source, lockfiles, additive migrations, instructions, generated API contracts, tests and screenshots. Runtime `.env`, API keys, account/database/object-store data, caches, installed dependencies and build outputs are excluded. The current functional specification describes delivered behavior; original design documents are marked historical references. The documentation refresh on 2026-10-29 changes no application behavior.
