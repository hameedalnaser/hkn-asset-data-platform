/* =====================================================================
   01_schemas_and_security.sql
   Schemas, roles, and least-privilege security for the HKN asset DW.

   JD security standards addressed here:
     * authenticated access      -> contained DB users + roles, no shared sa
     * least privilege           -> API role can only SELECT from dw views
     * defence against leakage   -> schema separation, views-only exposure,
                                     TDE (on by default in Azure SQL),
                                     dynamic data masking (see later files)

   Run order: this file first. Idempotent (safe to re-run).
   ===================================================================== */

----------------------------------------------------------------------
-- Schemas as security boundaries
----------------------------------------------------------------------
IF SCHEMA_ID('staging') IS NULL EXEC('CREATE SCHEMA staging');  -- raw, as-loaded
IF SCHEMA_ID('dw')      IS NULL EXEC('CREATE SCHEMA dw');       -- clean star schema
IF SCHEMA_ID('app')     IS NULL EXEC('CREATE SCHEMA app');      -- views the API reads
IF SCHEMA_ID('audit')   IS NULL EXEC('CREATE SCHEMA audit');    -- load/run logging
GO

----------------------------------------------------------------------
-- Roles (least privilege). Grant to users, never grant rights to users
-- directly, so access is auditable and revocable in one place.
----------------------------------------------------------------------

-- ETL role: the pipeline. May write staging + dw, read everything, log.
IF DATABASE_PRINCIPAL_ID('role_etl') IS NULL CREATE ROLE role_etl;
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::staging TO role_etl;
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dw      TO role_etl;
GRANT SELECT, INSERT                 ON SCHEMA::audit   TO role_etl;

-- API read role: the FastAPI service. SELECT on the app (views) schema ONLY.
-- It can NOT see staging, can NOT read dw base tables, can NOT write anything.
IF DATABASE_PRINCIPAL_ID('role_api_read') IS NULL CREATE ROLE role_api_read;
GRANT SELECT ON SCHEMA::app TO role_api_read;
-- Explicitly deny everything else as defence in depth.
DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::staging TO role_api_read;
DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dw      TO role_api_read;
GO

/* ---------------------------------------------------------------------
   Contained database users (Azure SQL best practice: use contained users,
   not server logins, so the DB is portable and access is self-contained).

   SECURITY: passwords are NOT in this file. Create the users by running
   sql/02_create_users.sql.template after substituting secrets from your
   environment — that template is gitignored. JD: "no credentials in code".
   --------------------------------------------------------------------- */
