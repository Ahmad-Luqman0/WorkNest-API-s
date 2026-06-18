-- ============================================================
-- WorkNest - Complete Database Migration & Stored Procedures
-- Run this entire file ONCE in SSMS against your WorkNest database
-- ============================================================
-- This script contains:
-- 1. Branch & Company Integration (BranchId, CompanyId columns)
-- 2. City Lookup Table Migration (WN_Cities table, CityId FK)
-- 3. Auto-Assignment Booking System (7 stored procedures)
-- 4. Core WorkNest Stored Procedures (22 procedures)
-- ============================================================

USE [WorkNest]
GO

PRINT '============================================================';
PRINT 'Starting WorkNest Complete Migration';
PRINT '============================================================';
GO

-- ============================================================
-- SECTION 1: Branch & Company Integration Schema Changes
-- ============================================================

PRINT 'Applying Branch & Company schema changes...';
GO

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
UPDATE dbo.WN_Locations
SET BranchId = CASE
    WHEN Id = (SELECT MIN(Id) FROM dbo.WN_Locations) THEN 267
    WHEN Id = (SELECT MIN(Id) + 1 FROM dbo.WN_Locations) THEN 268
    ELSE NULL
END
WHERE BranchId IS NULL;
GO

PRINT 'Branch & Company schema changes applied.';
GO

-- ============================================================
-- SECTION 2: City Lookup Table Migration
-- ============================================================

PRINT 'Creating City lookup table...';
GO

-- Create WN_Cities lookup table
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

-- Seed cities from existing WN_Locations.City text
INSERT INTO dbo.WN_Cities (Name, Status)
SELECT DISTINCT LTRIM(RTRIM(City)), 1
FROM dbo.WN_Locations
WHERE City IS NOT NULL AND LTRIM(RTRIM(City)) <> ''
  AND LTRIM(RTRIM(City)) NOT IN (SELECT Name FROM dbo.WN_Cities);
GO

-- Add CityId FK column to WN_Locations
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_Locations') AND name = 'CityId'
)
    ALTER TABLE dbo.WN_Locations ADD CityId INT NULL;
GO

-- Populate CityId from existing City text
UPDATE l
SET l.CityId = c.Id
FROM dbo.WN_Locations l
INNER JOIN dbo.WN_Cities c ON LTRIM(RTRIM(l.City)) = c.Name
WHERE l.CityId IS NULL;
GO

PRINT 'City lookup table created and populated.';
GO

-- ============================================================
-- SECTION 3: Wrapper & Lookup Stored Procedures
-- ============================================================

PRINT 'Creating wrapper stored procedures...';
GO

-- WN_Branches_GetList
CREATE OR ALTER PROCEDURE dbo.WN_Branches_GetList
    @CompanyId INT = 484
AS
BEGIN
    SET NOCOUNT ON;
    EXEC SAC400.dbo.Branches_GetIdbyCompanyId @CompanyId;
END
GO

-- WN_Companies_GetList
CREATE OR ALTER PROCEDURE dbo.WN_Companies_GetList
AS
BEGIN
    SET NOCOUNT ON;
    EXEC SAC400.dbo.Company_GetCompanyList;
END
GO

-- WN_Cities_GetList
CREATE OR ALTER PROCEDURE dbo.WN_Cities_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        Id     AS Id,
        IdGUID AS IdGuid,
        Name   AS Name,
        Status AS Status
    FROM dbo.WN_Cities WITH (NOLOCK)
    WHERE Status = 1
    ORDER BY Name ASC;
END
GO

PRINT 'Wrapper procedures created.';
GO

-- ============================================================
-- SECTION 4: Core WorkNest Stored Procedures
-- ============================================================

PRINT 'Creating core WorkNest stored procedures...';
GO

-- ── 1. WN_Users_GetByEmail ────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Users_GetByEmail
    @Email NVARCHAR(256)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Email = @Email;
END
GO

-- ── 2. WN_Users_Insert ───────────────────────────────────
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

-- ── 3. WN_Users_Update ───────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Users_Update
    @FirstName   NVARCHAR(MAX),
    @LastName    NVARCHAR(MAX),
    @PhoneNumber NVARCHAR(MAX),
    @Id          INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_Users
    SET Name        = LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
        PhoneNumber = @PhoneNumber,
        UpdatedOn   = GETDATE()
    WHERE Id = @Id;
END
GO

-- ── 4. WN_Users_GetList ───────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Users_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        u.IdGUID      AS IdGuid,
        u.Id          AS Id,
        u.Email       AS Email,
        u.Name        AS Name,
        u.PhoneNumber AS Phone,
        u.CreatedOn   AS CreatedAt,
        u.RoleId      AS Roles_Int,
        u.CompanyId   AS CompanyId
    FROM dbo.WN_Users u WITH (NOLOCK)
    ORDER BY u.CreatedOn DESC;
END
GO

-- ── 5. WN_Locations_GetList ───────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Locations_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        l.Id            AS Id,
        l.IdGUID        AS IdGuid,
        l.Name          AS Name,
        l.Address       AS Address,
        l.CityId        AS CityId,
        c.Name          AS CityName,
        l.OpeningTime   AS OpeningTime,
        l.ClosingTime   AS ClosingTime,
        l.Status        AS Status,
        l.BranchId      AS BranchId,
        b.[Description] AS BranchName,
        b.[Code]        AS BranchCode
    FROM dbo.WN_Locations l WITH (NOLOCK)
    LEFT JOIN dbo.WN_Cities  c WITH (NOLOCK) ON l.CityId   = c.Id
    LEFT JOIN SAC400.dbo.Branches b WITH (NOLOCK) ON l.BranchId = b.Id
    WHERE l.Status = 1;
END
GO

-- ── 6. WN_SpaceTypes_GetList ──────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_SpaceTypes_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id           AS Id,
           IdGUID       AS IdGuid,
           Description  AS Name,
           Capacity     AS Capacity,
           HourlyAllowed AS HourlyAllowed,
           Status       AS Status
    FROM dbo.WN_SpaceTypes WITH (NOLOCK)
    WHERE Status = 1;
END
GO

-- ── 7. WN_Spaces_GetList ──────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT s.IdGUID          AS IdGuid,
           s.Id              AS Id,
           s.Name            AS Name,
           s.Code            AS Code,
           s.Floor           AS Floor,
           s.Description     AS Description,
           s.PricePerDay     AS PricePerDay,
           s.PricePerHour    AS PricePerHour,
           s.Amenities       AS Amenities,
           s.ImageUrl        AS ImageUrl,
           s.Status          AS Status,
           l.IdGUID          AS LocationIdGuid,
           l.Name            AS LocationName,
           st.IdGUID         AS SpaceTypeIdGuid,
           st.Description    AS SpaceTypeName,
           st.Capacity       AS Capacity
    FROM dbo.WN_Spaces s WITH (NOLOCK)
    LEFT JOIN dbo.WN_Locations l  WITH (NOLOCK) ON s.LocationId  = l.IdGUID
    LEFT JOIN dbo.WN_SpaceTypes st WITH (NOLOCK) ON s.SpaceTypeId = st.IdGUID
    WHERE s.Status != 0;
END
GO

-- ── 8. WN_Spaces_Insert ───────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_Insert
    @Name        NVARCHAR(255),
    @LocationId  UNIQUEIDENTIFIER,
    @SpaceTypeId UNIQUEIDENTIFIER,
    @Code        NVARCHAR(50),
    @Description NVARCHAR(MAX),
    @Floor       NVARCHAR(50),
    @PricePerDay  DECIMAL(10,2),
    @PricePerHour DECIMAL(10,2),
    @ImageUrl    NVARCHAR(500),
    @Amenities   NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.WN_Spaces
        (IdGUID, Name, LocationId, SpaceTypeId, Code, Description, Floor,
         PricePerDay, PricePerHour, ImageUrl, Amenities, Status, CreatedOn)
    VALUES
        (NEWID(), @Name, @LocationId, @SpaceTypeId, @Code, @Description, @Floor,
         @PricePerDay, @PricePerHour, @ImageUrl, @Amenities, 1, GETDATE());

    SELECT SCOPE_IDENTITY() AS NewId;
END
GO

-- ── 9. WN_Spaces_Update ───────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_Update
    @Id          INT,
    @Name        NVARCHAR(255),
    @LocationId  UNIQUEIDENTIFIER,
    @SpaceTypeId UNIQUEIDENTIFIER,
    @Code        NVARCHAR(50),
    @Description NVARCHAR(MAX),
    @Floor       NVARCHAR(50),
    @PricePerDay  DECIMAL(10,2),
    @PricePerHour DECIMAL(10,2),
    @ImageUrl    NVARCHAR(500),
    @Amenities   NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_Spaces
    SET Name        = @Name,
        LocationId  = @LocationId,
        SpaceTypeId = @SpaceTypeId,
        Code        = @Code,
        Description = @Description,
        Floor       = @Floor,
        PricePerDay  = @PricePerDay,
        PricePerHour = @PricePerHour,
        ImageUrl    = @ImageUrl,
        Amenities   = @Amenities,
        UpdatedOn   = GETDATE()
    WHERE Id = @Id;
END
GO

-- ── 10. WN_GalleryImages_GetList ──────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_GalleryImages_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT g.IdGUID   AS IdGuid,
           g.Id       AS Id,
           g.Title    AS Title,
           g.ImageUrl AS ImageUrl,
           g.SortOrder AS SortOrder,
           g.IsActive AS IsActive
    FROM dbo.WN_GalleryImages g WITH (NOLOCK)
    WHERE g.IsActive = 1
    ORDER BY g.SortOrder ASC;
END
GO

-- ── 11. WN_PricingPlans_GetList ───────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_PricingPlans_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT p.IdGUID        AS IdGuid,
           p.Id            AS Id,
           p.Name          AS Name,
           ISNULL(p.Price, 0) AS Price,
           p.BillingCycle  AS BillingCycle,
           p.IncludesHours AS IncludesHours,
           p.IsActive      AS IsActive,
           p.Description   AS Description,
           f.FeatureName   AS FeatureName
    FROM dbo.WN_PricingPlans p WITH (NOLOCK)
    LEFT JOIN dbo.WN_PlanFeatures f WITH (NOLOCK) ON p.Id = f.PlanId AND f.Status != 0
    WHERE p.IsActive = 1;
END
GO

-- ── 12. WN_Bookings_Insert ────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_Insert
    @UserId        INT,
    @SpaceId       INT,
    @StartDateTime DATETIME,
    @EndDateTime   DATETIME,
    @TotalAmount   DECIMAL(18,2),
    @Notes         NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID        UNIQUEIDENTIFIER;
    DECLARE @SpaceGUID       UNIQUEIDENTIFIER;
    DECLARE @NewBookingGUID  UNIQUEIDENTIFIER = NEWID();

    SELECT @UserGUID  = IdGUID FROM dbo.WN_Users  WITH (NOLOCK) WHERE Id = @UserId;
    SELECT @SpaceGUID = IdGUID FROM dbo.WN_Spaces WITH (NOLOCK) WHERE Id = @SpaceId;

    INSERT INTO dbo.WN_Bookings
        (IdGUID, BookingDate, UserGuid, SpaceGuid, StartDateTime, EndDateTime,
         TotalAmount, BookingStatus, Status, Notes, CreatedOn, CreatedBy)
    VALUES
        (@NewBookingGUID, GETDATE(), @UserGUID, @SpaceGUID, @StartDateTime, @EndDateTime,
         @TotalAmount, 1, 1, @Notes, GETDATE(), @UserGUID);

    SELECT SCOPE_IDENTITY() AS NewId, @NewBookingGUID AS NewIdGuid;
END
GO

-- ── 13. WN_Bookings_Cancel ────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_Cancel
    @BookingId INT,
    @UserId    INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    UPDATE dbo.WN_Bookings WITH (ROWLOCK)
    SET BookingStatus = 2,
        UpdatedOn     = GETDATE(),
        UpdatedBy     = @UserGUID
    WHERE Id = @BookingId AND UserGuid = @UserGUID;
END
GO

-- ── 14. WN_Bookings_GetListByUserId ──────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_GetListByUserId
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    SELECT b.IdGUID         AS IdGuid,
           b.Id             AS Id,
           s.Name           AS SpaceName,
           b.StartDateTime  AS StartDateTime,
           b.EndDateTime    AS EndDateTime,
           b.TotalAmount    AS TotalAmount,
           b.Notes          AS Notes,
           b.BookingDate    AS CreatedAt,
           CASE b.BookingStatus
               WHEN 1 THEN 'Pending'
               WHEN 2 THEN 'Cancelled'
               WHEN 3 THEN 'Rejected'
               WHEN 4 THEN 'Confirmed'
               ELSE 'Confirmed'
           END AS BookingStatus
    FROM dbo.WN_Bookings b WITH (NOLOCK)
    LEFT JOIN dbo.WN_Spaces s WITH (NOLOCK) ON b.SpaceGuid = s.IdGUID
    WHERE b.UserGuid = @UserGUID AND b.Status = 1
    ORDER BY b.BookingDate DESC;
END
GO

-- ── 15. WN_Bookings_GetList ───────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT b.IdGUID         AS IdGuid,
           b.Id             AS Id,
           u.Email          AS UserEmail,
           s.Name           AS SpaceName,
           b.StartDateTime  AS StartDateTime,
           b.EndDateTime    AS EndDateTime,
           b.TotalAmount    AS TotalAmount,
           b.Notes          AS Notes,
           b.BookingDate    AS CreatedAt,
           CASE b.BookingStatus
               WHEN 1 THEN 'Pending'
               WHEN 2 THEN 'Cancelled'
               WHEN 3 THEN 'Rejected'
               WHEN 4 THEN 'Confirmed'
               ELSE 'Confirmed'
           END AS BookingStatus
    FROM dbo.WN_Bookings b WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users  u WITH (NOLOCK) ON b.UserGuid  = u.IdGUID
    LEFT JOIN dbo.WN_Spaces s WITH (NOLOCK) ON b.SpaceGuid = s.IdGUID
    WHERE b.Status = 1
    ORDER BY b.BookingDate DESC;
END
GO

-- ── 16. WN_Payments_Insert ────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Payments_Insert
    @UserId         INT,
    @BookingId      INT,
    @Amount         DECIMAL(18,2),
    @PaymentMethod  NVARCHAR(100),
    @TransactionRef NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID    UNIQUEIDENTIFIER;
    DECLARE @BookingGUID UNIQUEIDENTIFIER;

    SELECT @UserGUID    = IdGUID FROM dbo.WN_Users    WITH (NOLOCK) WHERE Id = @UserId;
    SELECT @BookingGUID = IdGUID FROM dbo.WN_Bookings WITH (NOLOCK) WHERE Id = @BookingId;

    INSERT INTO dbo.WN_Payments
        (UserId, BookingId, Amount, Currency, PaymentMethod, PaymentStatus, TransactionRef, PaidAt, CreatedAt)
    VALUES
        (@UserGUID, @BookingGUID, @Amount, 'PKR', @PaymentMethod, 'Pending', @TransactionRef, NULL, GETDATE());

    DECLARE @NewId INT = SCOPE_IDENTITY();
    SELECT @NewId AS NewId,
           (SELECT IdGUID FROM dbo.WN_Payments WITH (NOLOCK) WHERE Id = @NewId) AS NewIdGuid;
END
GO

-- ── 17. WN_Payments_GetMyList ─────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Payments_GetMyList
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    SELECT p.IdGUID          AS IdGuid,
           p.Id              AS Id,
           p.Amount          AS Amount,
           p.PaymentMethod   AS PaymentMethod,
           p.PaymentStatus   AS PaymentStatus,
           p.PaidAt          AS PaidAt,
           p.TransactionRef  AS ReferenceNumber,
           s.Name            AS WorkspaceName,
           b.StartDateTime   AS Start_Date,
           b.EndDateTime     AS End_Date
    FROM dbo.WN_Payments p WITH (NOLOCK)
    LEFT JOIN dbo.WN_Bookings b WITH (NOLOCK) ON p.BookingId = b.IdGUID
    LEFT JOIN dbo.WN_Spaces   s WITH (NOLOCK) ON b.SpaceGuid = s.IdGUID
    WHERE p.UserId = @UserGUID
    ORDER BY p.CreatedAt DESC;
END
GO

-- ── 18. WN_Payments_GetList ───────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Payments_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT p.IdGUID         AS IdGuid,
           p.Id             AS Id,
           u.Email          AS UserEmail,
           p.Amount         AS Amount,
           p.PaymentMethod  AS PaymentMethod,
           p.PaymentStatus  AS PaymentStatus,
           p.TransactionRef AS TransactionRef,
           p.PaidAt         AS PaidAt
    FROM dbo.WN_Payments p WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users u WITH (NOLOCK) ON p.UserId = u.IdGUID
    ORDER BY p.CreatedAt DESC;
END
GO

-- ── 19. WN_Payments_UpdateStatusByRef ────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Payments_UpdateStatusByRef
    @TransactionRef NVARCHAR(100),
    @PaymentStatus  NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_Payments
    SET PaymentStatus = @PaymentStatus,
        PaidAt        = CASE WHEN @PaymentStatus = 'Paid' THEN GETDATE() ELSE PaidAt END
    WHERE TransactionRef = @TransactionRef;
END
GO

-- ── 20. WN_BookTour_Insert ────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_BookTour_Insert
    @Name        NVARCHAR(255),
    @Email       NVARCHAR(256),
    @Message     NVARCHAR(MAX),
    @PhoneNumber NVARCHAR(20),
    @UserId      INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @NewGUID  UNIQUEIDENTIFIER = NEWID();
    DECLARE @UserGUID UNIQUEIDENTIFIER = NULL;

    IF @UserId IS NOT NULL
        SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    INSERT INTO dbo.WN_BookTour (IdGUID, Name, Email, Message, PhoneNumber, CreatedOn, CreatedBy)
    VALUES (@NewGUID, @Name, @Email, @Message, @PhoneNumber, GETDATE(), @UserGUID);

    SELECT SCOPE_IDENTITY() AS NewId, @NewGUID AS NewIdGuid;
END
GO

-- ── 21. WN_Contacts_GetList ───────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Contacts_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT b.IdGUID     AS IdGuid,
           b.Id         AS Id,
           b.Name       AS FullName,
           b.Email      AS Email,
           b.PhoneNumber AS Phone,
           b.Message    AS Message,
           b.CreatedOn  AS CreatedAt,
           b.CreatedBy  AS CreatedBy,
           b.Status     AS Status
    FROM dbo.WN_BookTour b WITH (NOLOCK)
    WHERE b.Status = 1
    ORDER BY b.CreatedOn DESC;
END
GO

-- ── 22. WN_Memberships_GetList ────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Memberships_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT m.IdGUID    AS IdGuid,
           m.Id        AS NumericId,
           u.Email     AS UserEmail,
           pp.Name     AS PlanName,
           pp.Price    AS PlanPrice,
           pp.BillingCycle AS PlanCycle,
           m.StartDate AS StartDate,
           m.EndDate   AS EndDate,
           m.Status    AS Status
    FROM dbo.WN_Memberships m WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users        u  WITH (NOLOCK) ON m.UserGuid = u.IdGUID
    LEFT JOIN dbo.WN_PricingPlans pp WITH (NOLOCK) ON m.PlanId   = pp.Id
    WHERE m.Status != 0
    ORDER BY m.StartDate DESC;
END
GO

PRINT 'Core stored procedures created.';
GO

-- ============================================================
-- SECTION 5: Auto-Assignment Booking System Procedures
-- ============================================================

PRINT 'Creating auto-assignment booking system procedures...';
GO

-- ── 1. WN_GetAvailableSpaces ──────────────────────────────
IF OBJECT_ID('WN_GetAvailableSpaces', 'P') IS NOT NULL
    DROP PROCEDURE WN_GetAvailableSpaces
GO

CREATE PROCEDURE WN_GetAvailableSpaces
    @SpaceType NVARCHAR(100),
    @StartDateTime DATETIME,
    @EndDateTime DATETIME
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @SpaceTypeId INT;
    
    SELECT @SpaceTypeId = Id 
    FROM WN_SpaceTypes 
    WHERE Description = @SpaceType AND Status = 1;
    
    IF @SpaceTypeId IS NULL
    BEGIN
        RAISERROR('Invalid space type', 16, 1);
        RETURN;
    END
    
    SELECT 
        s.Id,
        s.IdGUID,
        s.Name,
        s.Code,
        s.PricePerDay,
        s.PricePerHour,
        st.Description AS SpaceType,
        l.Name AS LocationName,
        CASE 
            WHEN @SpaceType LIKE '%Private%' AND s.Code LIKE '30%%' THEN 1
            WHEN @SpaceType LIKE '%Shared%' AND s.Code LIKE '31%%' THEN 1  
            WHEN @SpaceType LIKE '%Meeting%' AND s.Code LIKE '32%%' THEN 1
            ELSE 2
        END AS Priority,
        CASE 
            WHEN ISNUMERIC(SUBSTRING(s.Code, 3, LEN(s.Code)-2)) = 1 
            THEN CAST(SUBSTRING(s.Code, 3, LEN(s.Code)-2) AS INT)
            ELSE 999
        END AS CodeNumber
    FROM WN_Spaces s
    INNER JOIN WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
    INNER JOIN WN_Locations l ON s.LocationId = l.IdGUID
    WHERE s.SpaceTypeId = @SpaceTypeId 
        AND s.Status = 1
        AND s.Id NOT IN (
            SELECT DISTINCT b.SpaceId
            FROM WN_Bookings b
            WHERE b.BookingStatus IN (1, 4)
                AND (
                    (@StartDateTime >= b.StartDateTime AND @StartDateTime < b.EndDateTime) OR
                    (@EndDateTime > b.StartDateTime AND @EndDateTime <= b.EndDateTime) OR
                    (@StartDateTime <= b.StartDateTime AND @EndDateTime >= b.EndDateTime)
                )
        )
    ORDER BY Priority ASC, CodeNumber ASC;
END
GO

-- ── 2. WN_CreateBookingWithAutoAssignment ─────────────────
IF OBJECT_ID('WN_CreateBookingWithAutoAssignment', 'P') IS NOT NULL
    DROP PROCEDURE WN_CreateBookingWithAutoAssignment
GO

CREATE PROCEDURE WN_CreateBookingWithAutoAssignment
    @Email NVARCHAR(255),
    @SpaceType NVARCHAR(100),
    @StartDateTime DATETIME,
    @EndDateTime DATETIME,
    @Notes NVARCHAR(MAX) = '',
    @TotalAmount DECIMAL(10,2) = 0,
    @PaymentMethod NVARCHAR(50) = NULL,
    @PaymentRef NVARCHAR(100) = NULL,
    @BookingId INT OUTPUT,
    @BookingGuid UNIQUEIDENTIFIER OUTPUT,
    @AssignedSpaceId INT OUTPUT,
    @AssignedSpaceName NVARCHAR(255) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRANSACTION;
    
    BEGIN TRY
        DECLARE @UserId INT,
