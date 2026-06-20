-- ============================================================
-- WorkNest Smart Booking Migration v3
-- Database: SAC400
-- Run order: 1) this file
-- ============================================================
USE [SAC400]
GO

PRINT 'Starting v3...';
GO

-- Drop old SPs
IF OBJECT_ID('dbo.WN_Booking_Create',            'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_Create;
GO
IF OBJECT_ID('dbo.WN_Booking_AssignClosestSpace', 'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_AssignClosestSpace;
GO
IF OBJECT_ID('dbo.WN_Booking_GetAvailableSpaces', 'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_GetAvailableSpaces;
GO
IF OBJECT_ID('dbo.WN_Booking_CheckOverlap',       'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_CheckOverlap;
GO
IF OBJECT_ID('dbo.WN_Spaces_GenerateInventory',   'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_GenerateInventory;
GO
IF OBJECT_ID('dbo.WN_Spaces_UpdateConfig',        'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_UpdateConfig;
GO
IF OBJECT_ID('dbo.WN_Spaces_GetConfig',           'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_GetConfig;
GO
PRINT 'Old SPs dropped.';
GO

-- ============================================================
-- WN_SpaceConfig table
-- ============================================================
IF OBJECT_ID('dbo.WN_SpaceConfig', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.WN_SpaceConfig (
        Id                INT           IDENTITY(1,1) PRIMARY KEY,
        SpaceCategory     NVARCHAR(20)  NOT NULL,
        SpaceTypeId       INT           NULL,
        TotalSpaces       INT           NOT NULL DEFAULT 0,
        CodePrefix        NVARCHAR(5)   NOT NULL,
        MinCode           INT           NOT NULL,
        DefaultCapacities NVARCHAR(50)  NULL,
        OpeningTime       NVARCHAR(5)   NOT NULL DEFAULT '08:00',
        ClosingTime       NVARCHAR(5)   NOT NULL DEFAULT '20:00',
        UpdatedOn         DATETIME      NULL,
        UpdatedBy         NVARCHAR(255) NULL
    );
    PRINT 'WN_SpaceConfig created.';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.WN_SpaceConfig') AND name = 'SpaceTypeId')
    ALTER TABLE dbo.WN_SpaceConfig ADD SpaceTypeId INT NULL;
GO

-- Seed: SpaceTypeId 2=Co-Working, 1=Private Office, 3=Meeting Room
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Shared')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,SpaceTypeId,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Shared',2,60,'30',3001,NULL,'08:00','20:00');
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Private')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,SpaceTypeId,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Private',1,50,'31',3101,'3,4,5','08:00','20:00');
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Meeting')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,SpaceTypeId,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Meeting',3,10,'32',3201,'7,8,9,10','08:00','20:00');

UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 2 WHERE SpaceCategory = 'Shared'  AND SpaceTypeId IS NULL;
UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 1 WHERE SpaceCategory = 'Private' AND SpaceTypeId IS NULL;
UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 3 WHERE SpaceCategory = 'Meeting' AND SpaceTypeId IS NULL;
GO
PRINT 'WN_SpaceConfig seeded.';
GO

-- ============================================================
-- Fix existing space codes to numeric convention
-- Co-Working(Id=2)->3001, Private(Id=1)->3101, Meeting(Id=3)->3201
-- Private 1 (Id=8)->3102
-- ============================================================
DECLARE @PvtGuid UNIQUEIDENTIFIER;
DECLARE @CwsGuid UNIQUEIDENTIFIER;
DECLARE @MtgGuid UNIQUEIDENTIFIER;
SELECT @PvtGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 1;
SELECT @CwsGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 2;
SELECT @MtgGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 3;
UPDATE dbo.WN_Spaces SET Code = '3101', SpaceTypeId = @PvtGuid WHERE Id = 1;
UPDATE dbo.WN_Spaces SET Code = '3001', SpaceTypeId = @CwsGuid WHERE Id = 2;
UPDATE dbo.WN_Spaces SET Code = '3201', SpaceTypeId = @MtgGuid WHERE Id = 3;
UPDATE dbo.WN_Spaces SET Code = '3102', SpaceTypeId = @PvtGuid WHERE Id = 8;
GO
PRINT 'Space codes updated.';
GO

-- ============================================================
-- WN_Spaces_GetConfig
-- ============================================================
CREATE PROCEDURE dbo.WN_Spaces_GetConfig
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, SpaceCategory, SpaceTypeId, TotalSpaces, CodePrefix, MinCode,
           DefaultCapacities, OpeningTime, ClosingTime, UpdatedOn, UpdatedBy
    FROM dbo.WN_SpaceConfig
    ORDER BY Id;
END
GO

-- ============================================================
-- WN_Spaces_UpdateConfig
-- ============================================================
CREATE PROCEDURE dbo.WN_Spaces_UpdateConfig
    @SpaceCategory     NVARCHAR(20),
    @TotalSpaces       INT,
    @DefaultCapacities NVARCHAR(50)  = NULL,
    @OpeningTime       NVARCHAR(5)   = NULL,
    @ClosingTime       NVARCHAR(5)   = NULL,
    @AdminEmail        NVARCHAR(255) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_SpaceConfig
    SET TotalSpaces       = @TotalSpaces,
        DefaultCapacities = ISNULL(@DefaultCapacities, DefaultCapacities),
        OpeningTime       = ISNULL(@OpeningTime, OpeningTime),
        ClosingTime       = ISNULL(@ClosingTime, ClosingTime),
        UpdatedOn         = GETUTCDATE(),
        UpdatedBy         = @AdminEmail
    WHERE SpaceCategory   = @SpaceCategory;
    SELECT @@ROWCOUNT AS AffectedRows;
END
GO

-- ============================================================
-- WN_Spaces_GenerateInventory
-- ============================================================
CREATE PROCEDURE dbo.WN_Spaces_GenerateInventory
    @SpaceCategory NVARCHAR(20),
    @LocationId    INT,
    @PricePerHour  DECIMAL(10,2) = 0,
    @PricePerDay   DECIMAL(10,2) = 0
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @TotalSpaces   INT;
    DECLARE @MinCode       INT;
    DECLARE @MaxCode       INT;
    DECLARE @Counter       INT;
    DECLARE @CodeStr       NVARCHAR(10);
    DECLARE @SpaceName     NVARCHAR(100);
    DECLARE @LocationGuid  UNIQUEIDENTIFIER;
    DECLARE @SpaceTypeGuid UNIQUEIDENTIFIER;
    DECLARE @SpaceTypeId   INT;

    SELECT @TotalSpaces = TotalSpaces, @MinCode = MinCode, @SpaceTypeId = SpaceTypeId
    FROM   dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;

    IF @TotalSpaces IS NULL
    BEGIN RAISERROR('Unknown SpaceCategory',16,1); RETURN; END

    SELECT @LocationGuid  = IdGUID FROM dbo.WN_Locations  WHERE Id = @LocationId  AND Status = 1;
    SELECT @SpaceTypeGuid = IdGUID FROM dbo.WN_SpaceTypes  WHERE Id = @SpaceTypeId AND Status = 1;

    IF @LocationGuid IS NULL OR @SpaceTypeGuid IS NULL
    BEGIN RAISERROR('Invalid LocationId or SpaceTypeId',16,1); RETURN; END

    SET @MaxCode = @MinCode + @TotalSpaces - 1;
    SET @Counter = @MinCode;
    WHILE @Counter <= @MaxCode
    BEGIN
        SET @CodeStr   = CAST(@Counter AS NVARCHAR(10));
        SET @SpaceName = @SpaceCategory + ' Space ' + @CodeStr;
        IF NOT EXISTS (SELECT 1 FROM dbo.WN_Spaces WHERE Code = @CodeStr AND SpaceTypeId = @SpaceTypeGuid AND Status != 0)
        BEGIN
            INSERT INTO dbo.WN_Spaces (IdGUID,Name,LocationId,SpaceTypeId,Code,PricePerHour,PricePerDay,Status,CreatedOn)
            VALUES (NEWID(),@SpaceName,@LocationGuid,@SpaceTypeGuid,@CodeStr,@PricePerHour,@PricePerDay,1,GETUTCDATE());
        END
        SET @Counter = @Counter + 1;
    END
    UPDATE dbo.WN_Spaces SET Status=0
    WHERE SpaceTypeId=@SpaceTypeGuid AND TRY_CAST(Code AS INT)>@MaxCode AND TRY_CAST(Code AS INT)>=@MinCode;
    SELECT @TotalSpaces AS TotalConfigured;
END
GO

-- ============================================================
-- WN_Booking_CheckOverlap
-- Resolves SpaceGuid from WN_Spaces then checks WN_Bookings
-- ============================================================
CREATE PROCEDURE dbo.WN_Booking_CheckOverlap
    @SpaceNumericId   INT,
    @StartDT          DATETIME,
    @EndDT            DATETIME,
    @ExcludeBookingId INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @SG UNIQUEIDENTIFIER;
    SELECT @SG = IdGUID FROM dbo.WN_Spaces WHERE Id = @SpaceNumericId;
    IF @SG IS NULL BEGIN SELECT 0 AS IsOverlapping; RETURN; END
    IF EXISTS (
        SELECT 1 FROM dbo.WN_Bookings bk
        WHERE bk.SpaceGuid = @SG
          AND bk.BookingStatus IN (1,4)
          AND (@ExcludeBookingId IS NULL OR bk.Id != @ExcludeBookingId)
          AND @StartDT < bk.EndDateTime
          AND @EndDT   > bk.StartDateTime
    )
        SELECT 1 AS IsOverlapping;
    ELSE
        SELECT 0 AS IsOverlapping;
END
GO

-- ============================================================
-- WN_Booking_GetAvailableSpaces
-- Filters by SpaceTypeId (no code range dependency)
-- ============================================================
CREATE PROCEDURE dbo.WN_Booking_GetAvailableSpaces
    @SpaceCategory NVARCHAR(20),
    @StartDT       DATETIME,
    @EndDT         DATETIME,
    @Capacity      INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @SpaceTypeId INT;
    DECLARE @STGuid      UNIQUEIDENTIFIER;

    SELECT @SpaceTypeId = SpaceTypeId FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;
    IF @SpaceTypeId IS NULL BEGIN RAISERROR('Unknown SpaceCategory',16,1); RETURN; END
    SELECT @STGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = @SpaceTypeId;

    SELECT
        s.Id,
        s.IdGUID,
        s.Name,
        s.Code,
        s.PricePerDay,
        s.PricePerHour,
        st.Description          AS SpaceType,
        st.Capacity             AS Capacity,
        l.Name                  AS LocationName,
        TRY_CAST(s.Code AS INT) AS CodeNumber
    FROM  dbo.WN_Spaces     s
    JOIN  dbo.WN_SpaceTypes st ON st.IdGUID = s.SpaceTypeId
    JOIN  dbo.WN_Locations  l  ON l.IdGUID  = s.LocationId
    WHERE s.Status = 1
      AND s.SpaceTypeId = @STGuid
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
            SELECT 1 FROM dbo.WN_Bookings bk
            WHERE bk.SpaceGuid = s.IdGUID
              AND bk.BookingStatus IN (1,4)
              AND @StartDT < bk.EndDateTime
              AND @EndDT   > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC, s.Id ASC;
END
GO

-- ============================================================
-- WN_Booking_AssignClosestSpace
-- ============================================================
CREATE PROCEDURE dbo.WN_Booking_AssignClosestSpace
    @SpaceCategory NVARCHAR(20),
    @StartDT       DATETIME,
    @EndDT         DATETIME,
    @Capacity      INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @SpaceTypeId INT;
    DECLARE @STGuid      UNIQUEIDENTIFIER;

    SELECT @SpaceTypeId = SpaceTypeId FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;
    IF @SpaceTypeId IS NULL BEGIN RAISERROR('Unknown SpaceCategory',16,1); RETURN; END
    SELECT @STGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = @SpaceTypeId;

    SELECT TOP 1
        s.Id, s.IdGUID, s.Name, s.Code, st.Capacity, l.Name AS LocationName
    FROM  dbo.WN_Spaces     s
    JOIN  dbo.WN_SpaceTypes st ON st.IdGUID = s.SpaceTypeId
    JOIN  dbo.WN_Locations  l  ON l.IdGUID  = s.LocationId
    WHERE s.Status = 1
      AND s.SpaceTypeId = @STGuid
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
            SELECT 1 FROM dbo.WN_Bookings bk
            WHERE bk.SpaceGuid = s.IdGUID
              AND bk.BookingStatus IN (1,4)
              AND @StartDT < bk.EndDateTime
              AND @EndDT   > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC, s.Id ASC;
END
GO

-- ============================================================
-- WN_Booking_Create
-- ============================================================
CREATE PROCEDURE dbo.WN_Booking_Create
    @Email             NVARCHAR(255),
    @SpaceCategory     NVARCHAR(20),
    @StartDT           DATETIME,
    @EndDT             DATETIME,
    @Notes             NVARCHAR(MAX)    = '',
    @TotalAmount       DECIMAL(10,2)    = 0,
    @PaymentMethod     NVARCHAR(50)     = NULL,
    @PaymentRef        NVARCHAR(100)    = NULL,
    @Capacity          INT              = NULL,
    @BookingId         INT              OUTPUT,
    @BookingGuid       UNIQUEIDENTIFIER OUTPUT,
    @AssignedSpaceId   INT              OUTPUT,
    @AssignedSpaceName NVARCHAR(255)    OUTPUT,
    @AssignedSpaceCode NVARCHAR(20)     OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserId      INT;
    DECLARE @UserGuid    UNIQUEIDENTIFIER;
    DECLARE @SpaceId     INT;
    DECLARE @SpaceGuid   UNIQUEIDENTIFIER;
    DECLARE @SpaceTypeId INT;
    DECLARE @STGuid      UNIQUEIDENTIFIER;

    SELECT @UserId = Id, @UserGuid = IdGUID FROM dbo.WN_Users WHERE Email = @Email;
    IF @UserId IS NULL BEGIN RAISERROR('User not found',16,1); RETURN; END

    SELECT @SpaceTypeId = SpaceTypeId FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;
    IF @SpaceTypeId IS NULL BEGIN RAISERROR('Unknown SpaceCategory',16,1); RETURN; END

    SELECT @STGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = @SpaceTypeId;

    BEGIN TRANSACTION;

    SELECT TOP 1
        @SpaceId           = s.Id,
        @SpaceGuid         = s.IdGUID,
        @AssignedSpaceName = s.Name,
        @AssignedSpaceCode = s.Code
    FROM  dbo.WN_Spaces     s WITH (UPDLOCK)
    JOIN  dbo.WN_SpaceTypes st ON st.IdGUID = s.SpaceTypeId
    WHERE s.Status = 1
      AND s.SpaceTypeId = @STGuid
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
            SELECT 1 FROM dbo.WN_Bookings bk
            WHERE bk.SpaceGuid = s.IdGUID
              AND bk.BookingStatus IN (1,4)
              AND @StartDT < bk.EndDateTime
              AND @EndDT   > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC, s.Id ASC;

    IF @SpaceId IS NULL
    BEGIN
        ROLLBACK TRANSACTION;
        RAISERROR('No available space for the requested period',16,1);
        RETURN;
    END

    SET @BookingGuid = NEWID();

    INSERT INTO dbo.WN_Bookings
        (IdGUID, UserGuid, SpaceGuid, StartDateTime, EndDateTime,
         Notes, TotalAmount, BookingStatus, Status, BookingDate, CreatedOn, CreatedBy)
    VALUES
        (@BookingGuid, @UserGuid, @SpaceGuid, @StartDT, @EndDT,
         @Notes, @TotalAmount, 1, 1, GETUTCDATE(), GETUTCDATE(), @UserGuid);

    SET @BookingId       = SCOPE_IDENTITY();
    SET @AssignedSpaceId = @SpaceId;

    IF @PaymentMethod IS NOT NULL AND @TotalAmount > 0
    BEGIN
        INSERT INTO dbo.WN_Payments
            (IdGUID, UserId, BookingId, Amount, Currency,
             PaymentMethod, PaymentStatus, TransactionRef, CreatedAt)
        VALUES
            (NEWID(), @UserGuid, @BookingGuid, @TotalAmount, 'PKR',
             @PaymentMethod, 'Pending', @PaymentRef, GETUTCDATE());
    END

    COMMIT TRANSACTION;
END
GO

PRINT 'ALL DONE - Migration v3 completed successfully.';
GO
