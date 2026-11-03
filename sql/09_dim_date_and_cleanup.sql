/* =====================================================================
   09_dim_date_and_cleanup.sql
   - usp_ensure_date: make sure a given date exists in dim_date (called by
     the pipeline before merging a day's facts).
   - usp_purge_staging_batch: drop a batch's staging rows after a successful
     merge, so staging stays a short-lived landing zone, not a second copy
     of the warehouse.
   ===================================================================== */

CREATE OR ALTER PROCEDURE dw.usp_ensure_date @d DATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM dw.dim_date WHERE [date] = @d)
        INSERT INTO dw.dim_date
            (date_key, [date], [year], [quarter], [month], month_name,
             [day], day_name, is_weekend)
        VALUES (
            CONVERT(INT, FORMAT(@d,'yyyyMMdd')), @d,
            YEAR(@d), DATEPART(QUARTER, @d), MONTH(@d), DATENAME(MONTH, @d),
            DAY(@d), DATENAME(WEEKDAY, @d),
            CASE WHEN DATENAME(WEEKDAY, @d) IN ('Friday','Saturday') THEN 1 ELSE 0 END
        );
END
GO

CREATE OR ALTER PROCEDURE dw.usp_purge_staging_batch
    @report_type SYSNAME, @load_batch_id BIGINT AS
BEGIN
    SET NOCOUNT ON;
    -- @report_type is validated against a whitelist so it can't be abused
    -- as dynamic SQL injection, even though it comes from our own code.
    IF @report_type NOT IN ('production','deferment','power','maintenance')
    BEGIN
        RAISERROR('Unknown report_type %s', 16, 1, @report_type);
        RETURN;
    END
    DECLARE @sql NVARCHAR(200) =
        N'DELETE FROM staging.' + QUOTENAME(@report_type) +
        N' WHERE load_batch_id = @bid';
    EXEC sp_executesql @sql, N'@bid BIGINT', @bid = @load_batch_id;
END
GO
