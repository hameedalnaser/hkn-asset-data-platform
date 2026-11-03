/* =====================================================================
   05_dw_facts.sql
   Fact tables. Grain is documented on each. Columnstore-friendly,
   indexed for the common date/field slicing the dashboards do.
   Each fact carries load_batch_id for lineage back to the source file.
   Idempotent DDL.
   ===================================================================== */

----------------------------------------------------------------------
-- fact_production: grain = one well per field per day.
----------------------------------------------------------------------
IF OBJECT_ID('dw.fact_production') IS NULL
CREATE TABLE dw.fact_production (
    date_key       INT NOT NULL REFERENCES dw.dim_date(date_key),
    field_key      INT NOT NULL REFERENCES dw.dim_field(field_key),
    well_key       INT NOT NULL REFERENCES dw.dim_well(well_key),
    gross_rate_bbl DECIMAL(12,2) NULL,
    bsw_fraction   DECIMAL(6,4)  NULL,
    oil_rate_bbl   DECIMAL(12,2) NULL,
    is_down        BIT           NOT NULL DEFAULT 0,
    load_batch_id  BIGINT        NOT NULL,
    CONSTRAINT pk_fact_production PRIMARY KEY (date_key, well_key)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_fact_production_field_date')
CREATE INDEX ix_fact_production_field_date ON dw.fact_production(field_key, date_key);
GO

----------------------------------------------------------------------
-- fact_facility_daily: grain = one field per day (inlet/outlet/tank/export).
----------------------------------------------------------------------
IF OBJECT_ID('dw.fact_facility_daily') IS NULL
CREATE TABLE dw.fact_facility_daily (
    date_key            INT NOT NULL REFERENCES dw.dim_date(date_key),
    field_key           INT NOT NULL REFERENCES dw.dim_field(field_key),
    facility_inlet_bbl  DECIMAL(12,2) NULL,
    facility_outlet_bbl DECIMAL(12,2) NULL,
    tank_opening_bbl    DECIMAL(12,2) NULL,
    tank_closing_bbl    DECIMAL(12,2) NULL,
    export_bbl          DECIMAL(12,2) NULL,
    flare_mscf          DECIMAL(12,2) NULL,
    load_batch_id       BIGINT        NOT NULL,
    CONSTRAINT pk_fact_facility_daily PRIMARY KEY (date_key, field_key)
);
GO

----------------------------------------------------------------------
-- fact_deferment: grain = one downtime event (field/day/cause/equipment).
----------------------------------------------------------------------
IF OBJECT_ID('dw.fact_deferment') IS NULL
CREATE TABLE dw.fact_deferment (
    deferment_key  BIGINT IDENTITY(1,1) PRIMARY KEY,
    date_key       INT NOT NULL REFERENCES dw.dim_date(date_key),
    field_key      INT NOT NULL REFERENCES dw.dim_field(field_key),
    equipment_key  INT NULL REFERENCES dw.dim_equipment(equipment_key),
    cause          NVARCHAR(40)  NOT NULL,
    downtime_hours DECIMAL(8,2)  NULL,
    deferred_bbl   DECIMAL(12,2) NULL,
    comment        NVARCHAR(400) NULL,
    load_batch_id  BIGINT        NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_fact_deferment_field_date')
CREATE INDEX ix_fact_deferment_field_date ON dw.fact_deferment(field_key, date_key);
GO

----------------------------------------------------------------------
-- fact_power: grain = one generator per field per day.
----------------------------------------------------------------------
IF OBJECT_ID('dw.fact_power') IS NULL
CREATE TABLE dw.fact_power (
    date_key       INT NOT NULL REFERENCES dw.dim_date(date_key),
    field_key      INT NOT NULL REFERENCES dw.dim_field(field_key),
    generator_key  INT NOT NULL REFERENCES dw.dim_generator(generator_key),
    capacity_mw    DECIMAL(8,2)  NULL,
    hours_run      DECIMAL(8,2)  NULL,
    avg_load_mw    DECIMAL(8,2)  NULL,
    fuel_gas_mscf  DECIMAL(12,2) NULL,
    diesel_litres  DECIMAL(12,2) NULL,
    trips          INT           NULL,
    load_batch_id  BIGINT        NOT NULL,
    CONSTRAINT pk_fact_power PRIMARY KEY (date_key, generator_key)
);
GO

----------------------------------------------------------------------
-- fact_maintenance: grain = one work order (as-of the report date it
-- was last seen). Idempotent on work_order.
----------------------------------------------------------------------
IF OBJECT_ID('dw.fact_maintenance') IS NULL
CREATE TABLE dw.fact_maintenance (
    work_order     NVARCHAR(60) NOT NULL PRIMARY KEY,
    date_key       INT NOT NULL REFERENCES dw.dim_date(date_key),
    field_key      INT NOT NULL REFERENCES dw.dim_field(field_key),
    equipment_key  INT NULL REFERENCES dw.dim_equipment(equipment_key),
    wo_type        NVARCHAR(20) NULL,
    priority       INT          NULL,
    created_date   DATE         NULL,
    status         NVARCHAR(20) NULL,
    pm_due_date    DATE         NULL,
    completed_date DATE         NULL,
    load_batch_id  BIGINT       NOT NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='ix_fact_maintenance_field')
CREATE INDEX ix_fact_maintenance_field ON dw.fact_maintenance(field_key, status);
GO
