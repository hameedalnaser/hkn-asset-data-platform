/* =====================================================================
   08_merge_procs.sql
   Stored procedures that move one load batch from staging into the dw
   star schema. MERGE on natural keys makes re-loading a day idempotent
   (update existing, insert new) instead of duplicating.

   Dimensions are upserted first so facts always find their keys. All
   procs take @load_batch_id so they only touch the rows just staged.

   JD: parameterised SQL (procs are parameterised), stored procedures,
   reconciled & documented loads. CREATE OR ALTER = idempotent deploy.
   ===================================================================== */

----------------------------------------------------------------------
-- Helper: ensure a field exists, return nothing (facts look it up).
-- Inlined per proc below for clarity.
----------------------------------------------------------------------

CREATE OR ALTER PROCEDURE dw.usp_merge_production @load_batch_id BIGINT AS
BEGIN
    SET NOCOUNT ON;

    -- upsert fields
    MERGE dw.dim_field AS t
    USING (SELECT DISTINCT field_name FROM staging.production
           WHERE load_batch_id = @load_batch_id) AS s
    ON t.field_name = s.field_name
    WHEN NOT MATCHED THEN INSERT (field_name) VALUES (s.field_name);

    -- upsert wells (exclude the FACILITY_TOTAL pseudo-row)
    MERGE dw.dim_well AS t
    USING (
        SELECT DISTINCT s.well AS well_name, f.field_key
        FROM staging.production s
        JOIN dw.dim_field f ON f.field_name = s.field_name
        WHERE s.load_batch_id = @load_batch_id AND s.well <> 'FACILITY_TOTAL'
    ) AS s
    ON t.field_key = s.field_key AND t.well_name = s.well_name
    WHEN NOT MATCHED THEN INSERT (well_name, field_key)
                         VALUES (s.well_name, s.field_key);

    -- fact_production (well-level rows)
    MERGE dw.fact_production AS t
    USING (
        SELECT CONVERT(INT, FORMAT(s.report_date,'yyyyMMdd')) AS date_key,
               f.field_key, w.well_key,
               s.gross_rate_bbl, s.bsw_fraction, s.oil_rate_bbl,
               CASE WHEN s.status = 'DOWN' THEN 1 ELSE 0 END AS is_down,
               s.load_batch_id
        FROM staging.production s
        JOIN dw.dim_field f ON f.field_name = s.field_name
        JOIN dw.dim_well  w ON w.field_key = f.field_key AND w.well_name = s.well
        WHERE s.load_batch_id = @load_batch_id AND s.well <> 'FACILITY_TOTAL'
    ) AS s
    ON t.date_key = s.date_key AND t.well_key = s.well_key
    WHEN MATCHED THEN UPDATE SET
        gross_rate_bbl = s.gross_rate_bbl, bsw_fraction = s.bsw_fraction,
        oil_rate_bbl = s.oil_rate_bbl, is_down = s.is_down,
        field_key = s.field_key, load_batch_id = s.load_batch_id
    WHEN NOT MATCHED THEN INSERT
        (date_key, field_key, well_key, gross_rate_bbl, bsw_fraction,
         oil_rate_bbl, is_down, load_batch_id)
        VALUES (s.date_key, s.field_key, s.well_key, s.gross_rate_bbl,
                s.bsw_fraction, s.oil_rate_bbl, s.is_down, s.load_batch_id);

    -- fact_facility_daily (the FACILITY_TOTAL row)
    MERGE dw.fact_facility_daily AS t
    USING (
        SELECT CONVERT(INT, FORMAT(s.report_date,'yyyyMMdd')) AS date_key,
               f.field_key, s.facility_inlet_bbl, s.facility_outlet_bbl,
               s.tank_opening_bbl, s.tank_closing_bbl, s.export_bbl,
               s.flare_mscf, s.load_batch_id
        FROM staging.production s
        JOIN dw.dim_field f ON f.field_name = s.field_name
        WHERE s.load_batch_id = @load_batch_id AND s.well = 'FACILITY_TOTAL'
    ) AS s
    ON t.date_key = s.date_key AND t.field_key = s.field_key
    WHEN MATCHED THEN UPDATE SET
        facility_inlet_bbl = s.facility_inlet_bbl,
        facility_outlet_bbl = s.facility_outlet_bbl,
        tank_opening_bbl = s.tank_opening_bbl,
        tank_closing_bbl = s.tank_closing_bbl,
        export_bbl = s.export_bbl, flare_mscf = s.flare_mscf,
        load_batch_id = s.load_batch_id
    WHEN NOT MATCHED THEN INSERT
        (date_key, field_key, facility_inlet_bbl, facility_outlet_bbl,
         tank_opening_bbl, tank_closing_bbl, export_bbl, flare_mscf, load_batch_id)
        VALUES (s.date_key, s.field_key, s.facility_inlet_bbl, s.facility_outlet_bbl,
                s.tank_opening_bbl, s.tank_closing_bbl, s.export_bbl,
                s.flare_mscf, s.load_batch_id);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_merge_power @load_batch_id BIGINT AS
BEGIN
    SET NOCOUNT ON;

    MERGE dw.dim_field AS t
    USING (SELECT DISTINCT field_name FROM staging.power
           WHERE load_batch_id = @load_batch_id) AS s
    ON t.field_name = s.field_name
    WHEN NOT MATCHED THEN INSERT (field_name) VALUES (s.field_name);

    MERGE dw.dim_generator AS t
    USING (
        SELECT DISTINCT s.generator AS generator_name, f.field_key
        FROM staging.power s JOIN dw.dim_field f ON f.field_name = s.field_name
        WHERE s.load_batch_id = @load_batch_id
    ) AS s
    ON t.field_key = s.field_key AND t.generator_name = s.generator_name
    WHEN NOT MATCHED THEN INSERT (generator_name, field_key)
                         VALUES (s.generator_name, s.field_key);

    MERGE dw.fact_power AS t
    USING (
        SELECT CONVERT(INT, FORMAT(s.report_date,'yyyyMMdd')) AS date_key,
               f.field_key, g.generator_key, s.capacity_mw, s.hours_run,
               s.avg_load_mw, s.fuel_gas_mscf, s.diesel_litres, s.trips,
               s.load_batch_id
        FROM staging.power s
        JOIN dw.dim_field     f ON f.field_name = s.field_name
        JOIN dw.dim_generator g ON g.field_key = f.field_key AND g.generator_name = s.generator
        WHERE s.load_batch_id = @load_batch_id
    ) AS s
    ON t.date_key = s.date_key AND t.generator_key = s.generator_key
    WHEN MATCHED THEN UPDATE SET
        capacity_mw = s.capacity_mw, hours_run = s.hours_run,
        avg_load_mw = s.avg_load_mw, fuel_gas_mscf = s.fuel_gas_mscf,
        diesel_litres = s.diesel_litres, trips = s.trips,
        field_key = s.field_key, load_batch_id = s.load_batch_id
    WHEN NOT MATCHED THEN INSERT
        (date_key, field_key, generator_key, capacity_mw, hours_run,
         avg_load_mw, fuel_gas_mscf, diesel_litres, trips, load_batch_id)
        VALUES (s.date_key, s.field_key, s.generator_key, s.capacity_mw,
                s.hours_run, s.avg_load_mw, s.fuel_gas_mscf, s.diesel_litres,
                s.trips, s.load_batch_id);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_merge_deferment @load_batch_id BIGINT AS
BEGIN
    SET NOCOUNT ON;

    MERGE dw.dim_field AS t
    USING (SELECT DISTINCT field_name FROM staging.deferment
           WHERE load_batch_id = @load_batch_id) AS s
    ON t.field_name = s.field_name
    WHEN NOT MATCHED THEN INSERT (field_name) VALUES (s.field_name);

    MERGE dw.dim_equipment AS t
    USING (SELECT DISTINCT equipment AS equipment_name FROM staging.deferment
           WHERE load_batch_id = @load_batch_id
             AND equipment IS NOT NULL AND equipment <> '') AS s
    ON t.equipment_name = s.equipment_name
    WHEN NOT MATCHED THEN INSERT (equipment_name) VALUES (s.equipment_name);

    -- deferment is event-grained; clear this batch's rows then insert
    -- (idempotent: re-running the same file replaces its events).
    DELETE df FROM dw.fact_deferment df WHERE df.load_batch_id = @load_batch_id;

    INSERT INTO dw.fact_deferment
        (date_key, field_key, equipment_key, cause, downtime_hours,
         deferred_bbl, comment, load_batch_id)
    SELECT CONVERT(INT, FORMAT(s.report_date,'yyyyMMdd')),
           f.field_key, e.equipment_key, s.cause, s.downtime_hours,
           s.deferred_bbl, s.comment, s.load_batch_id
    FROM staging.deferment s
    JOIN dw.dim_field f ON f.field_name = s.field_name
    LEFT JOIN dw.dim_equipment e ON e.equipment_name = s.equipment
    WHERE s.load_batch_id = @load_batch_id AND s.cause <> 'None';
END
GO

CREATE OR ALTER PROCEDURE dw.usp_merge_maintenance @load_batch_id BIGINT AS
BEGIN
    SET NOCOUNT ON;

    MERGE dw.dim_field AS t
    USING (SELECT DISTINCT field_name FROM staging.maintenance
           WHERE load_batch_id = @load_batch_id) AS s
    ON t.field_name = s.field_name
    WHEN NOT MATCHED THEN INSERT (field_name) VALUES (s.field_name);

    MERGE dw.dim_equipment AS t
    USING (SELECT DISTINCT equipment AS equipment_name FROM staging.maintenance
           WHERE load_batch_id = @load_batch_id
             AND equipment IS NOT NULL AND equipment <> '') AS s
    ON t.equipment_name = s.equipment_name
    WHEN NOT MATCHED THEN INSERT (equipment_name) VALUES (s.equipment_name);

    -- work_order is the natural key; latest report wins.
    MERGE dw.fact_maintenance AS t
    USING (
        SELECT s.work_order,
               CONVERT(INT, FORMAT(s.report_date,'yyyyMMdd')) AS date_key,
               f.field_key, e.equipment_key, s.wo_type, s.priority,
               s.created_date, s.status, s.pm_due_date, s.completed_date,
               s.load_batch_id
        FROM staging.maintenance s
        JOIN dw.dim_field f ON f.field_name = s.field_name
        LEFT JOIN dw.dim_equipment e ON e.equipment_name = s.equipment
        WHERE s.load_batch_id = @load_batch_id
    ) AS s
    ON t.work_order = s.work_order
    WHEN MATCHED THEN UPDATE SET
        date_key = s.date_key, field_key = s.field_key,
        equipment_key = s.equipment_key, wo_type = s.wo_type,
        priority = s.priority, created_date = s.created_date,
        status = s.status, pm_due_date = s.pm_due_date,
        completed_date = s.completed_date, load_batch_id = s.load_batch_id
    WHEN NOT MATCHED THEN INSERT
        (work_order, date_key, field_key, equipment_key, wo_type, priority,
         created_date, status, pm_due_date, completed_date, load_batch_id)
        VALUES (s.work_order, s.date_key, s.field_key, s.equipment_key,
                s.wo_type, s.priority, s.created_date, s.status,
                s.pm_due_date, s.completed_date, s.load_batch_id);
END
GO
