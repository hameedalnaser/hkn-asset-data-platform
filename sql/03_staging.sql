/* =====================================================================
   03_staging.sql
   Staging (landing) tables: raw rows exactly as read from each Excel
   report, plus load metadata. We validate and reconcile FROM staging
   INTO the dw layer, so staging is the audit trail of what actually
   arrived. Idempotent DDL.
   ===================================================================== */

----------------------------------------------------------------------
-- Load batch registry: one row per (file, run). Everything loaded is
-- stamped with a load_batch_id so you can trace, re-run, or roll back.
----------------------------------------------------------------------
IF OBJECT_ID('audit.load_batch') IS NULL
CREATE TABLE audit.load_batch (
    load_batch_id   BIGINT IDENTITY(1,1) PRIMARY KEY,
    source_file     NVARCHAR(260)  NOT NULL,
    report_type     NVARCHAR(40)   NOT NULL,   -- production/deferment/power/maintenance
    field_name      NVARCHAR(40)   NULL,
    report_date     DATE           NULL,
    row_count       INT            NULL,
    status          NVARCHAR(20)   NOT NULL DEFAULT 'STARTED',  -- STARTED/LOADED/VALIDATED/FAILED
    message         NVARCHAR(MAX)  NULL,
    started_at_utc  DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at_utc DATETIME2(0)   NULL,
    loaded_by       SYSNAME        NOT NULL DEFAULT SUSER_SNAME()  -- who ran it
);
GO

----------------------------------------------------------------------
-- Staging: production (well-level + facility total rows land together,
-- exactly as in the workbook; the dw split happens downstream).
----------------------------------------------------------------------
IF OBJECT_ID('staging.production') IS NULL
CREATE TABLE staging.production (
    load_batch_id        BIGINT        NOT NULL,
    report_date          DATE          NOT NULL,
    field_name           NVARCHAR(40)  NOT NULL,
    well                 NVARCHAR(40)  NOT NULL,
    gross_rate_bbl       DECIMAL(12,2) NULL,
    bsw_fraction         DECIMAL(6,4)  NULL,
    oil_rate_bbl         DECIMAL(12,2) NULL,
    status               NVARCHAR(10)  NULL,
    facility_inlet_bbl   DECIMAL(12,2) NULL,
    facility_outlet_bbl  DECIMAL(12,2) NULL,
    tank_opening_bbl     DECIMAL(12,2) NULL,
    tank_closing_bbl     DECIMAL(12,2) NULL,
    export_bbl           DECIMAL(12,2) NULL,
    flare_mscf           DECIMAL(12,2) NULL
);
GO

IF OBJECT_ID('staging.deferment') IS NULL
CREATE TABLE staging.deferment (
    load_batch_id   BIGINT        NOT NULL,
    report_date     DATE          NOT NULL,
    field_name      NVARCHAR(40)  NOT NULL,
    cause           NVARCHAR(40)  NOT NULL,
    equipment       NVARCHAR(80)  NULL,
    downtime_hours  DECIMAL(8,2)  NULL,
    deferred_bbl    DECIMAL(12,2) NULL,
    comment         NVARCHAR(400) NULL
);
GO

IF OBJECT_ID('staging.power') IS NULL
CREATE TABLE staging.power (
    load_batch_id   BIGINT        NOT NULL,
    report_date     DATE          NOT NULL,
    field_name      NVARCHAR(40)  NOT NULL,
    generator       NVARCHAR(40)  NOT NULL,
    capacity_mw     DECIMAL(8,2)  NULL,
    hours_run       DECIMAL(8,2)  NULL,
    avg_load_mw     DECIMAL(8,2)  NULL,
    fuel_gas_mscf   DECIMAL(12,2) NULL,
    diesel_litres   DECIMAL(12,2) NULL,
    trips           INT           NULL,
    status          NVARCHAR(20)  NULL
);
GO

IF OBJECT_ID('staging.maintenance') IS NULL
CREATE TABLE staging.maintenance (
    load_batch_id   BIGINT        NOT NULL,
    report_date     DATE          NOT NULL,
    field_name      NVARCHAR(40)  NOT NULL,
    work_order      NVARCHAR(60)  NOT NULL,
    equipment       NVARCHAR(80)  NULL,
    wo_type         NVARCHAR(20)  NULL,
    priority        INT           NULL,
    created_date    DATE          NULL,
    status          NVARCHAR(20)  NULL,
    pm_due_date     DATE          NULL,
    completed_date  DATE          NULL
);
GO
