/* =====================================================================
   06_app_views.sql
   The app schema: the ONLY objects the API's read-only user can see.
   Exposing views (not base tables) means:
     * we control exactly which columns leave the database (no SELECT *),
     * we can change the physical model without breaking the API,
     * least privilege is enforced at the schema boundary.
   These views pre-join dimensions so the API returns business-friendly rows.
   Idempotent via CREATE OR ALTER.
   ===================================================================== */

CREATE OR ALTER VIEW app.v_production_daily AS
SELECT d.[date]        AS report_date,
       f.field_name,
       w.well_name,
       p.gross_rate_bbl,
       p.bsw_fraction,
       p.oil_rate_bbl,
       p.is_down
FROM dw.fact_production p
JOIN dw.dim_date  d ON d.date_key  = p.date_key
JOIN dw.dim_field f ON f.field_key = p.field_key
JOIN dw.dim_well  w ON w.well_key  = p.well_key;
GO

CREATE OR ALTER VIEW app.v_facility_daily AS
SELECT d.[date] AS report_date, f.field_name,
       x.facility_inlet_bbl, x.facility_outlet_bbl,
       x.tank_opening_bbl, x.tank_closing_bbl,
       x.export_bbl, x.flare_mscf,
       -- reconciliation flag surfaced to the dashboard
       CASE WHEN x.export_bbl > x.facility_outlet_bbl + 1 THEN 1 ELSE 0 END
            AS export_exceeds_outlet_flag
FROM dw.fact_facility_daily x
JOIN dw.dim_date  d ON d.date_key  = x.date_key
JOIN dw.dim_field f ON f.field_key = x.field_key;
GO

CREATE OR ALTER VIEW app.v_deferment AS
SELECT d.[date] AS report_date, f.field_name,
       e.equipment_name, df.cause, df.downtime_hours, df.deferred_bbl
FROM dw.fact_deferment df
JOIN dw.dim_date  d ON d.date_key  = df.date_key
JOIN dw.dim_field f ON f.field_key = df.field_key
LEFT JOIN dw.dim_equipment e ON e.equipment_key = df.equipment_key;
GO

CREATE OR ALTER VIEW app.v_power_daily AS
SELECT d.[date] AS report_date, f.field_name, g.generator_name,
       pw.capacity_mw, pw.hours_run, pw.avg_load_mw,
       pw.fuel_gas_mscf, pw.diesel_litres, pw.trips,
       CASE WHEN pw.capacity_mw > 0
            THEN CAST(pw.avg_load_mw / pw.capacity_mw AS DECIMAL(5,3)) END
            AS load_factor
FROM dw.fact_power pw
JOIN dw.dim_date      d ON d.date_key      = pw.date_key
JOIN dw.dim_field     f ON f.field_key     = pw.field_key
JOIN dw.dim_generator g ON g.generator_key = pw.generator_key;
GO

CREATE OR ALTER VIEW app.v_maintenance AS
SELECT f.field_name, m.work_order, e.equipment_name,
       m.wo_type, m.priority, m.created_date, m.status,
       m.pm_due_date, m.completed_date,
       DATEDIFF(DAY, m.created_date,
                ISNULL(m.completed_date, CAST(SYSUTCDATETIME() AS DATE))) AS age_days
FROM dw.fact_maintenance m
JOIN dw.dim_field f ON f.field_key = m.field_key
LEFT JOIN dw.dim_equipment e ON e.equipment_key = m.equipment_key;
GO
