/* =====================================================================
   04_dw_dimensions.sql
   Conformed dimensions for the asset data warehouse. Surrogate keys for
   joins + natural (business) keys so loads are idempotent. Idempotent DDL.
   ===================================================================== */

----------------------------------------------------------------------
-- dim_date: one agreed calendar ("as-of dating" in the JD).
----------------------------------------------------------------------
IF OBJECT_ID('dw.dim_date') IS NULL
CREATE TABLE dw.dim_date (
    date_key     INT      NOT NULL PRIMARY KEY,   -- yyyymmdd
    [date]       DATE     NOT NULL UNIQUE,
    [year]       SMALLINT NOT NULL,
    [quarter]    TINYINT  NOT NULL,
    [month]      TINYINT  NOT NULL,
    month_name   NVARCHAR(12) NOT NULL,
    [day]        TINYINT  NOT NULL,
    day_name     NVARCHAR(12) NOT NULL,
    is_weekend   BIT      NOT NULL
);
GO

----------------------------------------------------------------------
-- dim_field: Sarsang / Atrush.
----------------------------------------------------------------------
IF OBJECT_ID('dw.dim_field') IS NULL
CREATE TABLE dw.dim_field (
    field_key    INT IDENTITY(1,1) PRIMARY KEY,
    field_name   NVARCHAR(40) NOT NULL UNIQUE
);
GO

----------------------------------------------------------------------
-- dim_well.
----------------------------------------------------------------------
IF OBJECT_ID('dw.dim_well') IS NULL
CREATE TABLE dw.dim_well (
    well_key     INT IDENTITY(1,1) PRIMARY KEY,
    well_name    NVARCHAR(40) NOT NULL,
    field_key    INT NOT NULL REFERENCES dw.dim_field(field_key),
    CONSTRAINT uq_well UNIQUE (field_key, well_name)
);
GO

----------------------------------------------------------------------
-- dim_equipment (shared by deferment + maintenance).
----------------------------------------------------------------------
IF OBJECT_ID('dw.dim_equipment') IS NULL
CREATE TABLE dw.dim_equipment (
    equipment_key  INT IDENTITY(1,1) PRIMARY KEY,
    equipment_name NVARCHAR(80) NOT NULL UNIQUE
);
GO

----------------------------------------------------------------------
-- dim_generator.
----------------------------------------------------------------------
IF OBJECT_ID('dw.dim_generator') IS NULL
CREATE TABLE dw.dim_generator (
    generator_key  INT IDENTITY(1,1) PRIMARY KEY,
    generator_name NVARCHAR(40) NOT NULL,
    field_key      INT NOT NULL REFERENCES dw.dim_field(field_key),
    CONSTRAINT uq_generator UNIQUE (field_key, generator_name)
);
GO
