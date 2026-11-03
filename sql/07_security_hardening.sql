/* =====================================================================
   07_security_hardening.sql
   Extra defence-in-depth against data leakage. Run after the model exists.
   Most of these are Azure SQL features; comments note what to enable in
   the portal vs. what runs here.
   ===================================================================== */

/* ---------------------------------------------------------------------
   1) Transparent Data Encryption (TDE) — data encrypted at rest.
      Azure SQL Database has TDE ON BY DEFAULT. Verify with:
        SELECT name, is_encrypted FROM sys.databases WHERE name = DB_NAME();
      (is_encrypted = 1). Nothing to do; documented for the interview.

   2) Encryption in transit — enforced by the connection string
      (Encrypt=yes;TrustServerCertificate=no in config.py). Azure SQL
      requires TLS; never disable it.

   3) Auditing — enable "Microsoft Defender for SQL" + "Auditing" on the
      server in the portal (or via az cli) to log access to a storage
      account. Free-tier friendly to leave Defender off for the demo, but
      MENTION it: it's how you'd detect anomalous access / exfiltration.
   --------------------------------------------------------------------- */

----------------------------------------------------------------------
-- 4) Dynamic Data Masking: mask free-text comment fields that could
--    carry sensitive operational notes, so a read-only user sees masked
--    values unless explicitly granted UNMASK. Demonstrates the principle.
----------------------------------------------------------------------
IF COL_LENGTH('dw.fact_deferment', 'comment') IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM sys.masked_columns
    WHERE object_id = OBJECT_ID('dw.fact_deferment') AND name = 'comment'
)
    ALTER TABLE dw.fact_deferment
    ALTER COLUMN comment ADD MASKED WITH (FUNCTION = 'partial(6, "***", 0)');
GO

-- The API read user must NOT be able to unmask. (role_api_read is not
-- granted UNMASK, so masking applies to it by default.) Explicit for clarity:
-- DENY UNMASK TO role_api_read;   -- (UNMASK is a grantable permission in Azure SQL)

/* ---------------------------------------------------------------------
   5) Row-Level Security (optional, documented): if different users should
      only see their own field (Sarsang vs Atrush), you'd add a security
      policy with a predicate function on field_key. Not needed for the
      single-analyst demo but good to mention.

   6) Principle recap for interview:
        - secrets out of code (env vars / Key Vault)
        - least privilege (role_api_read: SELECT on app views only)
        - views-only exposure (no base-table access, no SELECT *)
        - encryption at rest (TDE) + in transit (TLS)
        - masking sensitive columns, auditing access
        - Azure SQL firewall: allow only known IPs / Azure services
   --------------------------------------------------------------------- */
