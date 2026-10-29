# DataPilot local MVP — functional specification

Version: 0.3 · Updated: 2026-10-29 · Status: implemented local MVP

This document describes the shipped application and its acceptance criteria. It supersedes functional promises in the original six-week design. See the [API contract](../../packages/api-contract/openapi.json), [application guide](../../README.md), [security notes](../SECURITY.md) and [validation report](../VALIDATION.md) for supporting detail.

## 1. Purpose and workflow

DataPilot lets a signed-in user organize spreadsheet sources in workspaces, inspect quality, approve cleaning into new versions, map business measures, save reproducible analyses and dashboards, request skill-guided explanations, and export results. It runs locally through Docker Compose with PostgreSQL, Redis, MinIO, a background ingestion worker, FastAPI and Next.js.

The normal journey is **account → workspace → import → quality → cleaning preview → approval → analysis mapping → results/dashboard → explanation/export**. Cleaning is optional. Each file remains an independent dataset. The application does not automatically join data, convert currencies or infer business meaning.

## 2. Accounts, workspaces and permissions

| ID | Requirement and delivered behavior |
| --- | --- |
| ACC-01 | Register a local account with display name, email and a password of 12–128 characters. Duplicate emails are rejected; there is no seeded application account. |
| ACC-02 | Sign-in establishes an opaque HttpOnly, SameSite session. Sign-out invalidates it. Reloading or signing in again restores authorized workspaces and data. |
| ACC-03 | Create named workspaces and switch between active memberships. The creator becomes owner. |
| ACC-04 | Every workspace resource, version, analysis, dashboard, AI evidence request and download requires membership. Other users' identifiers cannot grant access. |
| ACC-05 | Owners/analysts may import/retry, preview/apply cleaning, create analyses and save dashboards. Viewers may inspect, request authorized explanations and export. AI settings belong to the individual account. |
| ACC-06 | Additive migrations preserve existing local accounts, password hashes, memberships and imports. Updates keep the existing `.env` and Docker volumes. |

Role checks exist; membership administration, invitations, password recovery, email verification and OIDC screens are outside this release.

## 3. Import and execution tracking

Select multiple files, drop files, or choose a folder using a compatible browser. The manifest lists selected files, sizes and relative paths and allows removal/clearing before submission. Unsupported files are visibly excluded. Folder selection includes supported nested files once; it is not a watcher or live connector.

| Limit or rule | Behavior |
| --- | --- |
| Formats | CSV and XLSX |
| Batch | 1–100 files; at most 100 MiB combined |
| Per file | Nonempty; at most 25 MiB |
| Dataset | At most 250,000 rows and 50 columns |
| XLSX worksheet | First visible worksheet; other sheets require separate files |
| Relative paths | Metadata only; traversal, duplicate paths and invalid control characters are rejected |
| Spreadsheet safety | Formula-containing XLSX files and suspicious/malformed containers are rejected; formulas/macros are never executed |

IMP-01: Upload progress precedes persisted per-file queued/running/completed/failed states. Each file has an independent result; a failed file does not discard successful peers.

IMP-02: Executions show progress and sanitized errors. Retry queues failed files only. Successful imports persist across later imports, reloads and sign-in sessions.

IMP-03: Original bytes, source SHA-256, source path and canonical Parquet are retained. File names and values do not become executable instructions or server filesystem paths.

## 4. Preview, quality and versions

The source view shows original row/column counts, up to 100 preview rows, inferred types, missing-value counts, completeness and provenance. Original preview remains available after cleaning. The workbench offers explicit dataset/version selection, including original and cleaned versions with parent lineage.

Quality findings cover missing values, exact duplicate rows, mixed numeric/text columns and formula-like text, with severity, affected counts and details. They do not establish business validity or modify data. Type inference preserves leading-zero identifiers. Long preview values may be truncated for display; calculations use canonical data rather than preview samples.

## 5. Controlled cleaning

CLN-01: Select a ready version and build an ordered plan of 1–20 allowlisted operations. Browser operations are:

| Operation | Behavior |
| --- | --- |
| `trim` | Trim string whitespace in one or all columns |
| `empty_to_null` | Convert blank/whitespace strings to null |
| `drop_duplicates` | Keep the first occurrence of each complete row |
| `drop_missing` | Remove rows null in a selected column; convert blanks first when needed |
| `fill_missing` | Replace nulls in one column with a user-supplied finite scalar |
| `rename` | Rename a column to a unique valid name |
| `cast_number` | Convert verified numeric text; reject invalid values, overflow or lossy decimals |

The API additionally supports `lowercase` and `uppercase`, which are not browser menu options. Median imputation, category remapping and date normalization from the original design are not implemented.

CLN-02: Preview processes the complete selected version and persists a proposed plan. It reports before/after row counts, removed rows, changed cells, per-operation summaries and up to 100 resulting rows. It does not create a cleaned version.

CLN-03: The browser requires the review/approval checkbox before saving. The authenticated apply request accepts the persisted plan ID, creates an immutable child version, refreshes profile/findings and records approval/audit data. It retains the original object and source hash.

CLN-04: Reapplying an applied plan returns its existing child. Concurrent applies serialize version numbering. Failed saves preserve originals and attempt to remove uncommitted derived objects. Invalid or lossy operations fail visibly.

## 6. Semantic mappings and deterministic analysis

ANL-01: Select a ready version, name the analysis and confirm at least one role: `revenue`, `cost`, `quantity`, `date` or `category`. Each role maps to a distinct existing column. Unrelated roles remain unmapped; column names do not imply business meaning.

ANL-02: Optional date filters use inclusive `date_from`/`date_to` bounds in `YYYY-MM-DD`; category filters use exact text matches. Filters require their corresponding mappings. Invalid bounds/unsupported filters are rejected. Date-filtered rows with invalid/missing dates are excluded. There is no timezone conversion.

ANL-03: Decimal computations use all rows in the selected canonical version, subject to saved filters. No model/user SQL or Python is executed.

| Metric | Definition |
| --- | --- |
| Rows | Number of rows included by filters |
| Revenue/cost/quantity | Sum valid values for each mapped role, independently excluding missing/invalid values |
| Average revenue per row | Revenue divided by number of valid revenue values |
| Profit | Sum revenue minus cost only where both values are valid |
| Margin (%) | 100 × profit divided by revenue on those same paired rows |

Zero-denominator ratios are null. Profit can differ from separately summed revenue minus cost when coverage differs. Evidence includes valid/missing/invalid counts, paired-row count, mappings, filters, version ID, original-source hash and calculation policy. That hash identifies original bytes, not cleaned Parquet. Units and comparable business granularity remain the user's responsibility.

ANL-04: Results persist metrics, category/date series, deterministic insights and evidence. Categories sort by descending row count with label tie-breaking; the API retains up to 50 groups. Date series contains up to the first 50 valid dates ascending. Browser charts show up to 30 supplied groups. Totals still use all filtered rows. Insights describe coverage, incomplete values and the largest category by row count; they do not establish causality.

## 7. Saved dashboards

DSH-01: Save a title and analysis reference. Fixed widgets display metric cards, category/date charts, insights and evidence. Lists return up to 200 recent analyses/dashboards.

DSH-02: Reload restores the saved snapshot. New imports/cleaned versions do not silently refresh historical figures. There is no arbitrary widget builder or drag-and-drop editor.

DSH-03: Saving a displayed dashboard uses the analysis visible in that snapshot, even when the independent analysis picker points elsewhere. A browser regression verifies this with two distinct analyses.

## 8. Skill-guided assistance and provider settings

AI-01: Per-account settings select local evidence mode, OpenAI, Anthropic or Google Gemini, with an editable provider model identifier and optional API key. Local mode fixes its model to `deterministic-v1`. Custom provider URLs and model discovery are unsupported.

AI-02: Keys are encrypted on the server; responses show only a saved-key flag and masked final four characters. Blank retains the same provider's key; explicit clear removes it; switching provider removes the old key unless a replacement is supplied. Keys are excluded from browser storage, prompts and audit metadata. The deployment encryption secret must remain stable across updates.

AI-03: Choose an application-owned data-quality, business-analysis or executive-summary skill. The UI shows its guidance. Arbitrary uploaded skill files are not installed or executed.

AI-04: Local mode returns deterministic evidence/guidance in English, French or Arabic without an external call. It explicitly does not interpret arbitrary questions, apply new filters or infer business causes.

AI-05: External mode requires request-specific consent. Its bounded payload includes the question, dataset/column names, quality counts and saved analysis aggregates/mapping/filters, excluding raw source rows. Names/questions/filter values may still be sensitive. The browser clears consent after each attempt.

AI-06: Fixed HTTPS provider hosts, redirect refusal and bounded time/output apply. Credential/model/quota/network errors are sanitized. Live use needs a valid provider key, permitted model and outbound access.

AI-07: Answers show provider/model, evidence and limitations. Questions/answers are stored in scoped conversations, but a history browser is not supplied. Generated text cannot execute code or apply cleaning. External numeric citations are requested but are not automatically verified by a claim-validation engine; users must check commentary against evidence. Provider adapters were tested with mocks, not live credentials.

## 9. Language, theme and responsive behavior

UX-01: English, French and Arabic controls localize normal navigation/forms/workflows. Arabic sets document language and RTL direction. Source names/values remain unchanged. Technical identifiers and some backend diagnostics can remain English.

UX-02: Light, dark and system themes cover account/workspace/workbench screens. Locale/theme persist in the same browser, not as synchronized account settings. Local answers follow the locale; external providers are instructed to use it.

UX-03: Loading, empty, validation, success and failure states are shown. Unauthorized/pending mutations are disabled. Chromium tests cover account/import workflows and Arabic mobile workbench width; complete accessibility certification and all-browser compatibility are not claimed.

## 10. Exports

EXP-01: Browser dataset exports are CSV/XLSX/JSON for the complete selected version. Analysis exports use their saved version and exact filters, regardless of an unrelated picker selection.

EXP-02: Analysis export options are CSV, XLSX, JSON, PDF and Power BI ZIP. CSV/XLSX/JSON retain Unicode. Spreadsheet exports neutralize formula-like text; JSON retains data values. Downloads require workspace authorization and use attachment headers.

EXP-03: PDF is a fixed English numerical report with evidence/provenance. Non-ASCII text is visibly escaped; localized typography and Arabic shaping are unsupported. The UI language does not change the PDF language.

EXP-04: The Power BI package contains portable data, mapping/provenance and Power Query/DAX guidance. It does not generate `.pbix`/`.pbit`, publish to Power BI or embed reports. Power BI Desktop interoperability was not tested here.

## 11. Persistence and operational boundary

PostgreSQL stores metadata; MinIO stores original/canonical objects. Redis/Celery dispatch background ingestion. Cleaning, analysis and exports are bounded synchronous API operations over canonical data. Completed computations may have job records, but the Executions browser tracks imports rather than every operation.

Startup applies additive migrations through `0004_ai_mvp` before readiness. Preserve `.env` and named volumes; `down -v` deletes local data. Canonical input/output has a 200 MiB workbench bound. No load-test SLA, historical-storage quota, automatic retention or backup guarantee is supplied. See [SECURITY.md](../SECURITY.md) for the parser sandbox and operational limits.

## 12. Acceptance and verification traceability

| Scenario | Acceptance criterion | Evidence |
| --- | --- | --- |
| Upgrade preservation | Existing password hashes, memberships and imports survive | `tests/integration/test_migrations.py` |
| Imports | CSV/XLSX, nested paths, independent malformed-file failure and access checks | `tests/integration/test_real_flow.py`, `scripts/real-flow-smoke.py`, `scripts/browser-smoke.mjs` |
| Cleaning | Approval creates a new version and preserves original rows/hash | `tests/test_data_compute.py`, `tests/integration/test_data_workflows.py`, `scripts/mvp-flow-smoke.py` |
| Metrics | Filters, role totals, paired profit/margin and exclusions match fixtures | `tests/test_data_compute.py`, `tests/test_data_mvp.py` |
| Dashboard | Reload and visible-snapshot saving retain the correct analysis | `scripts/browser-mvp-smoke.mjs` |
| AI credentials | Encryption, masking, retain/clear/switch and account isolation | `tests/test_ai_mvp.py`, `scripts/mvp-flow-smoke.py` |
| Providers | Fixed destinations, response parsing and sanitized failures against mocks | `tests/test_ai_mvp.py` |
| Exports | Real filtered data and valid CSV/XLSX/JSON/PDF/ZIP bytes | `tests/test_data_compute.py`, both MVP smoke scripts |
| Preferences | Dark persistence, French navigation, Arabic RTL/mobile without document overflow | `scripts/browser-mvp-smoke.mjs` |

The recorded release verification passed 81 Python tests, lint/format/type checks, Docker startup, real HTTP checks and both Chromium scripts. This documentation update does not introduce new product behavior. Exact dates and exclusions are in [VALIDATION.md](../VALIDATION.md).

## 13. Explicitly outside this release

- OIDC, recovery/verification, invitations and team administration.
- Watched folders, recurring imports, live connectors, automatic joins and multi-sheet selection.
- Arbitrary SQL/Python, automatic natural-language query planning, claim validation and causal inference.
- Currency conversion, forecasting, advanced statistical modeling and custom dashboard/report editing.
- Localized/Arabic-shaped PDF, native Power BI report/template binaries and embedding.
- Production certification, load guarantees, backup/restore drills, retention and provider spending controls.
