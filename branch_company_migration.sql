-- ============================================================
-- WorkNest: Branch & Company Integration Migration
-- Run this file ONCE in SSMS against your WorkNest database.
-- Requires cross-db access to SAC400 (Branches / Company tables).
-- ============================================================

USE [WorkNest]
GO

-- ── 1. Schema changes ─────────────────────────────────────

-- Add BranchId to WN_Locations (links to SAC400.dbo.Branches.Id)
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_Locations') AND name = 'BranchId'
)
    ALTER TABLE dbo.WN_Locations ADD BranchId INT NULL;
GO

-- Add CompanyId to WN_Users (default 484 = WorkNest company)
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_Users') AND name = 'CompanyId'
)
    ALTER TABLE dbo.WN_Users ADD CompanyId INT NULL DEFAULT 484;
GO

-- Seed CompanyId=484 on all existing users that have no company yet
UPDATE dbo.WN_Users SET CompanyId = 484 WHERE CompanyId IS NULL;
GO

-- Seed BranchId on existing locations by matching known branch codes:
--   267 = Head Office WorkNest (0001)
--   268 = F7 Markaz           (0002)
-- Map first location -> 267, second -> 268 (adjust as needed)
-- This is a safe no-op if BranchId is already set.
UPDATE dbo.WN_Locations
SET BranchId = CASE
    WHEN Id = (SELECT MIN(Id) FROM dbo.WN_Locations) THEN 267
    WHEN Id = (SELECT MIN(Id) + 1 FROM dbo.WN_Locations) THEN 268
    ELSE NULL
END
WHERE BranchId IS NULL;
GO

-- ── 2. WN_Branches_GetList ────────────────────────────────
-- Wraps SAC400.dbo.Branches_GetIdbyCompanyId for a given company.
-- Returns the two WorkNest branches (CompanyId = 484).
CREATE OR ALTER PROCEDURE dbo.WN_Branches_GetList
    @CompanyId INT = 484
AS
BEGIN
    SET NOCOUNT ON;
    EXEC SAC400.dbo.Branches_GetIdbyCompanyId @CompanyId;
END
GO

-- ── 3. WN_Companies_GetList ───────────────────────────────
-- Thin wrapper around SAC400.dbo.Company_GetCompanyList
CREATE OR ALTER PROCEDURE dbo.WN_Companies_GetList
AS
BEGIN
    SET NOCOUNT ON;
    EXEC SAC400.dbo.Company_GetCompanyList;
END
GO

-- ── 4. WN_Locations_GetList (updated) ────────────────────
-- Now includes BranchId, BranchCode, BranchDescription from SAC400
CREATE OR ALTER PROCEDURE dbo.WN_Locations_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        l.Id            AS id,
        l.IdGUID        AS idGuid,
        l.Name          AS name,
        l.Address       AS address,
        l.City          AS city,
        l.OpeningTime   AS openingTime,
        l.ClosingTime   AS closingTime,
        l.Status        AS status,
        l.BranchId      AS branchId,
        b.[Id]          AS branchNumericId,
        b.[Description] AS branchName,
        b.[Code]        AS branchCode
    FROM dbo.WN_Locations l WITH (NOLOCK)
    LEFT JOIN SAC400.dbo.Branches b WITH (NOLOCK) ON l.BranchId = b.Id
    WHERE l.Status = 1;
END
GO

-- ── 5. WN_Users_Insert (updated) ─────────────────────────
-- Stamps CompanyId = 484 on every new user automatically
CREATE OR ALTER PROCEDURE dbo.WN_Users_Insert
    @FirstName   NVARCHAR(MAX),
    @LastName    NVARCHAR(MAX),
    @UserName    NVARCHAR(256),
    @Email       NVARCHAR(256),
    @PhoneNumber NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ExistingId INT;
    SELECT @ExistingId = Id FROM dbo.WN_Users WITH (NOLOCK) WHERE Email = @Email;

    IF @ExistingId IS NOT NULL
    BEGIN
        UPDATE dbo.WN_Users
        SET Name        = LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
            PhoneNumber = @PhoneNumber,
            UpdatedOn   = GETDATE()
        WHERE Id = @ExistingId;

        SELECT @ExistingId AS NewId,
               (SELECT IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @ExistingId) AS NewIdGuid;
    END
    ELSE
    BEGIN
        DECLARE @NewUserGUID UNIQUEIDENTIFIER = NEWID();
        INSERT INTO dbo.WN_Users
            (IdGUID, Name, CreatedOn, UserName, Email, PhoneNumber, CompanyId)
        VALUES
            (@NewUserGUID,
             LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
             GETDATE(), @UserName, @Email, @PhoneNumber, 484);

        SELECT SCOPE_IDENTITY() AS NewId, @NewUserGUID AS NewIdGuid;
    END
END
GO

-- ── 6. WN_Users_GetList (updated) ────────────────────────
-- Now includes companyId so the admin panel can show it
CREATE OR ALTER PROCEDURE dbo.WN_Users_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        u.IdGUID      AS idGuid,
        u.Id          AS id,
        u.Email       AS email,
        u.Name        AS name,
        u.PhoneNumber AS phone,
        u.CreatedOn   AS createdAt,
        u.RoleId      AS roles_int,
        u.CompanyId   AS companyId
    FROM dbo.WN_Users u WITH (NOLOCK)
    ORDER BY u.CreatedOn DESC;
END
GO

PRINT 'Branch & Company migration applied successfully.';
GO
