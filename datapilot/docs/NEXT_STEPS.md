# After the local MVP

The current release includes local accounts, workspaces, multi-file/folder CSV/XLSX imports, isolated background ingestion, immutable original files, previews and quality findings. It also includes approved cleaning previews and new versions, user-confirmed analytics mappings with numerical evidence, saved analyses/dashboards, fixed AI skills with local or optional external providers, encrypted per-account model/key settings, English/French/Arabic UI, dark mode, and CSV/XLSX/JSON/PDF/Power BI handoff exports.

The following are later increments, not requirements for using this local MVP:

1. Managed OIDC, account recovery/email verification, invitations, team administration and production abuse controls.
2. Automated retention, quotas across historical versions, orphan/session cleanup, backup and restoration drills.
3. A richer dashboard editor, additional statistical methods and user-defined report layouts. Current dashboards are saved analysis snapshots and the PDF is a fixed English numerical report.
4. Live database connectors, verified joins or merges, recurring imports and watched folders. Current folder imports are one-time selections; each supported file remains an independent dataset.
5. Broader deployment hardening, stronger process isolation for a production pilot, dependency/container scanning and tested multi-host operations.
6. Extended provider compatibility and real-provider acceptance testing with the deployment's own provider accounts, model access and network configuration. Current provider request/response behavior is covered by mocked tests; local mode needs no external credentials.

AI uses fixed skill instructions and bounded dataset evidence. It does not execute arbitrary Python or SQL, silently alter data, infer a column's business meaning, or generate a native Power BI `.pbix` file. The Power BI export is an explicit package of data and import guidance.

Keep your existing `.env`, encryption secret and named Docker volumes when updating. Never use `docker compose down -v` as an upgrade step: it deletes local data. See the root README for startup and workflows, `SECURITY.md` for the local deployment boundary, and `VALIDATION.md` for checks actually performed.
