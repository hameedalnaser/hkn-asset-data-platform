# Database layer

Azure SQL Database. Run the scripts **in numeric order**. All DDL is idempotent (safe to re-run).

| # | File | Purpose |
|---|------|---------|
| 01 | `01_schemas_and_security.sql` | Schemas (`staging`, `dw`, `app`, `audit`) + least-privilege roles |
| 02 | `02_create_users.sql.template` | Template → copy to `.sql`, fill passwords, run, delete. **Gitignored when filled.** |
| 03 | `03_staging.sql` | Raw landing tables + `audit.load_batch` lineage registry |
| 04 | `04_dw_dimensions.sql` | Conformed dimensions (date, field, well, equipment, generator) |
| 05 | `05_dw_facts.sql` | Fact tables (production, facility, deferment, power, maintenance) |
| 06 | `06_app_views.sql` | Business views — the **only** objects the API user can read |
| 07 | `07_security_hardening.sql` | Masking, TDE/TLS/audit notes, RLS notes |
| 08 | `08_merge_procs.sql` | `usp_merge_*` stored procs: idempotent MERGE staging→dw |
| 09 | `09_dim_date_and_cleanup.sql` | `usp_ensure_date`, `usp_purge_staging_batch` |

## Design

Two-layer model: **staging** (raw, as-loaded, one row per source row, stamped with `load_batch_id`) → **dw** (clean star schema). The pipeline validates and reconciles *from* staging *into* dw, so staging is the audit trail of what arrived. Facts carry `load_batch_id` for lineage back to the exact source file and run.

Grain of each fact is documented in `05_dw_facts.sql`. Natural keys + `MERGE` (in the pipeline's stored procs) make loads idempotent: re-running a day's file updates rather than duplicates.

## Security model (JD: "no credentials in code, parameterised SQL, authenticated access")

- **Schema separation as a boundary.** `role_api_read` can `SELECT` on `app` views only; it is explicitly `DENY`-ed on `staging` and `dw`. The pipeline uses `role_etl`. The server admin login is never used by app code.
- **Views-only exposure.** The API never sees base tables or `SELECT *`; views pin exactly which columns leave the DB.
- **No secrets in git.** Passwords live in `.env` / App Service settings / (ideally) Azure Key Vault. Only `02_...template` is committed.
- **Encryption.** TDE at rest (on by default in Azure SQL) + TLS in transit (`Encrypt=yes` in the connection string).
- **Dynamic data masking** on free-text `comment`; `role_api_read` is not granted `UNMASK`.
- **Firewall + auditing** configured at the Azure SQL server level (see step 4 and `07`).
