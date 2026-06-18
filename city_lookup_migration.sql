-- ============================================================
-- WorkNest: City Lookup Integration Migration
-- Run ONCE in SSMS against your WorkNest database.
-- ============================================================

USE [WorkNest]
GO

-- ── 1. Create WN_Cities lookup table ─────────────────────

IF OBJECT_ID('dbo.WN_Cities', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.WN_Cities (
        Id      INT           IDENTITY(1,1) PRIMARY KEY,
        IdGUID  UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
        Name    NVARCHAR(255) NOT NULL,
        Status  INT           NOT NULL DEFAULT 1
    );
END
GO

-- ── 2. Seed cities from existing WN_Locations.City text ──

INSERT INTO dbo.WN_Cities (Name, Status)
SELECT DISTINCT LTRIM(RTRIM(City)), 1
FROM dbo.WN_Locations
WHERE City IS NOT NULL AND LTRIM(RTRIM(City)) <> ''
  AND LTRIM(RTRIM(City)) NOT IN (SELECT Name FROM dbo.WN_Cities);
GO

-- ── 3. Add CityId FK column to WN_Locations ──────────────

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_Locations') AND name = 'CityId'
)
    ALTER TABLE dbo.WN_Locations ADD CityId INT NULL;
GO

-- ── 4. Populate CityId from existing City text ───────────

UPDATE l
SET l.CityId = c.Id
FROM dbo.WN_Locations l
INNER JOIN dbo.WN_Cities c ON LTRIM(RTRIM(l.City)) = c.Name
WHERE l.CityId IS NULL;
GO

-- ── 5. WN_Cities_GetList ──────────────────────────────────

CREATE OR ALTER PROCEDURE dbo.WN_Cities_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        Id     AS id,
        IdGUID AS idGuid,
        Name   AS name,
        Status AS status
    FROM dbo.WN_Cities WITH (NOLOCK)
    WHERE Status = 1
    ORDER BY Name ASC;
END
GO

-- ── 6. WN_Locations_GetList (updated) ────────────────────
-- Returns CityId + cityName instead of raw City text.
-- Still JOINs SAC400 branches from prior migration.

CREATE OR ALTER PROCEDURE dbo.WN_Locations_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        l.Id            AS id,
        l.IdGUID        AS idGuid,
        l.Name          AS name,
        l.Address       AS address,
        l.CityId        AS cityId,
        c.Name          AS cityName,
        l.OpeningTime   AS openingTime,
        l.ClosingTime   AS closingTime,
        l.Status        AS status,
        l.BranchId      AS branchId,
        b.[Description] AS branchName,
        b.[Code]        AS branchCode
    FROM dbo.WN_Locations l WITH (NOLOCK)
    LEFT JOIN dbo.WN_Cities  c WITH (NOLOCK) ON l.CityId   = c.Id
    LEFT JOIN SAC400.dbo.Branches b WITH (NOLOCK) ON l.BranchId = b.Id
    WHERE l.Status = 1;
END
GO

PRINT 'City lookup migration applied successfully.';
GO
