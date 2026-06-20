-- ============================================================
-- WorkNest Smart Booking - Space Config Migration v2
-- Database: SAC400
-- Run this file in SSMS: File > Open > wn_smart_booking_v2.sql
-- ============================================================
USE [SAC400]
GO

PRINT 'Starting WN Smart Booking Migration v2...';
GO

-- Step 1: Drop old SPs
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
PRINT 'Step 1 done: Old SPs dropped.';
GO

-- Step 2: Create WN_SpaceConfig table
IF OBJECT_ID('dbo.WN_SpaceConfig', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.WN_SpaceConfig (
        Id                INT           IDENTITY(1,1) PRIMARY KEY,
        SpaceCategory     NVARCHAR(20)  NOT NULL,
        TotalSpaces       INT           NOT NULL DEFAULT 0,
        CodePrefix        NVARCHAR(5)   NOT NULL,
        MinCode           INT           NOT NULL,
        DefaultCapacities NVARCHAR(50)  NULL,
        OpeningTime       NVARCHAR(5)   NOT NULL DEFAULT '08:00',
        ClosingTime       NVARCHAR(5)   NOT NULL DEFAULT '20:00',
        UpdatedOn         DATETIME      NULL,
        UpdatedBy         NVARCHAR(255) NULL
    );
    PRINT 'WN_SpaceConfig table created.';
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Shared')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Shared', 60, '30', 3001, NULL, '08:00', '20:00');
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Private')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Private', 50, '31', 3101, '3,4,5', '08:00', '20:00');
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Meeting')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory,TotalSpaces,CodePrefix,MinCode,DefaultCapacities,OpeningTime,ClosingTime)
    VALUES ('Meeting', 10, '32', 3201, '7,8,9,10', '08:00', '20:00');
GO
PRINT 'Step 2 done: WN_SpaceConfig seeded.';
GO

-- Step 3: WN_Spaces_GetConfig
CREATE PROCEDURE dbo.WN_Spaces_GetConfig
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, SpaceCategory, TotalSpaces, CodePrefix, MinCode,
           DefaultCapacities, OpeningTime, ClosingTime, UpdatedOn, UpdatedBy
    FROM dbo.WN_SpaceConfig
    ORDER BY Id;
END
GO
PRINT 'Step 3 done: WN_Spaces_GetConfig created.';
GO

-- Step 4: WN_Spaces_UpdateConfig
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
    WHERE SpaceCategory = @SpaceCategory;
    SELECT @@ROWCOUNT AS AffectedRows;
END
GO
PRINT 'Step 4 done: WN_Spaces_UpdateConfig created.';
GO

-- Step 5: WN_Spaces_GenerateInventory
CREATE PROCEDURE dbo.WN_Spaces_GenerateInventory
    @SpaceCategory NVARCHAR(20),
    @SpaceTypeId   INT,
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

    SELECT @TotalSpaces = TotalSpaces, @MinCode = MinCode
    FROM   dbo.WN_SpaceConfig
    WHERE  SpaceCategory = @SpaceCategory;

    IF @TotalSpaces IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory', 16, 1);
        RETURN;
    END

    SELECT @LocationGuid  = IdGUID FROM dbo.WN_Locations WHERE Id = @LocationId  AND Status = 1;
    SELECT @SpaceTypeGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = @SpaceTypeId AND Status = 1;

    IF @LocationGuid IS NULL OR @SpaceTypeGuid IS NULL
    BEGIN
        RAISERROR('Invalid LocationId or SpaceTypeId', 16, 1);
        RETURN;
    END

    SET @MaxCode = @MinCode + @TotalSpaces - 1;
    SET @Counter = @MinCode;

    WHILE @Counter <= @MaxCode
    BEGIN
        SET @CodeStr   = CAST(@Counter AS NVARCHAR(10));
        SET @SpaceName = @SpaceCategory + ' Space ' + @CodeStr;
        IF NOT EXISTS (
            SELECT 1 FROM dbo.WN_Spaces
            WHERE Code = @CodeStr AND SpaceTypeId = @SpaceTypeGuid AND Status != 0
        )
        BEGIN
            INSERT INTO dbo.WN_Spaces
                (IdGUID, Name, LocationId, SpaceTypeId, Code, PricePerHour, PricePerDay, Status, CreatedOn)
            VALUES
                (NEWID(), @SpaceName, @LocationGuid, @SpaceTypeGuid,
                 @CodeStr, @PricePerHour, @PricePerDay, 1, GETUTCDATE());
        END
        SET @Counter = @Counter + 1;
    END

    UPDATE dbo.WN_Spaces
    SET Status = 0
    WHERE SpaceTypeId = @SpaceTypeGuid
      AND TRY_CAST(Code AS INT) > @MaxCode
      AND TRY_CAST(Code AS INT) >= @MinCode;

    SELECT @TotalSpaces AS TotalConfigured;
END
GO
PRINT 'Step 5 done: WN_Spaces_GenerateInventory created.';
GO

-- Step 6: WN_Booking_CheckOverlap
-- WN_Bookings has no SpaceId column. It stores space as SpaceGuid.
-- We first resolve SpaceGuid from WN_Spaces, then query WN_Bookings.
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
    IF @SG IS NULL
    BEGIN
        SELECT 0 AS IsOverlapping;
        RETURN;
    END
    IF EXISTS (
        SELECT 1
        FROM   dbo.WN_Bookings bk
        WHERE  bk.SpaceGuid        = @SG
          AND  bk.BookingStatus   IN (1, 4)
          AND  (@ExcludeBookingId IS NULL OR bk.Id != @ExcludeBookingId)
          AND  @StartDT            < bk.EndDateTime
          AND  @EndDT              > bk.StartDateTime
    )
        SELECT 1 AS IsOverlapping;
    ELSE
        SELECT 0 AS IsOverlapping;
END
GO
PRINT 'Step 6 done: WN_Booking_CheckOverlap created.';
GO

-- Step 7: WN_Booking_GetAvailableSpaces
-- Uses NOT EXISTS correlated against WN_Bookings.SpaceGuid
CREATE PROCEDURE dbo.WN_Booking_GetAvailableSpaces
    @SpaceCategory NVARCHAR(20),
    @StartDT       DATETIME,
    @EndDT         DATETIME,
    @Capacity      INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @MinCode     INT;
    DECLARE @MaxCode     INT;
    DECLARE @TotalSpaces INT;

    SELECT @MinCode = MinCode, @TotalSpaces = TotalSpaces
    FROM   dbo.WN_SpaceConfig
    WHERE  SpaceCategory = @SpaceCategory;

    IF @MinCode IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory', 16, 1);
        RETURN;
    END
    SET @MaxCode = @MinCode + @TotalSpaces - 1;

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
      AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
              SELECT 1
              FROM   dbo.WN_Bookings bk
              WHERE  bk.SpaceGuid      = s.IdGUID
                AND  bk.BookingStatus IN (1, 4)
                AND  @StartDT          < bk.EndDateTime
                AND  @EndDT            > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC;
END
GO
PRINT 'Step 7 done: WN_Booking_GetAvailableSpaces created.';
GO

-- Step 8: WN_Booking_AssignClosestSpace
CREATE PROCEDURE dbo.WN_Booking_AssignClosestSpace
    @SpaceCategory NVARCHAR(20),
    @StartDT       DATETIME,
    @EndDT         DATETIME,
    @Capacity      INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @MinCode     INT;
    DECLARE @MaxCode     INT;
    DECLARE @TotalSpaces INT;

    SELECT @MinCode = MinCode, @TotalSpaces = TotalSpaces
    FROM   dbo.WN_SpaceConfig
    WHERE  SpaceCategory = @SpaceCategory;

    IF @MinCode IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory', 16, 1);
        RETURN;
    END
    SET @MaxCode = @MinCode + @TotalSpaces - 1;

    SELECT TOP 1
        s.Id,
        s.IdGUID,
        s.Name,
        s.Code,
        st.Capacity,
        l.Name AS LocationName
    FROM  dbo.WN_Spaces     s
    JOIN  dbo.WN_SpaceTypes st ON st.IdGUID = s.SpaceTypeId
    JOIN  dbo.WN_Locations  l  ON l.IdGUID  = s.LocationId
    WHERE s.Status = 1
      AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
              SELECT 1
              FROM   dbo.WN_Bookings bk
              WHERE  bk.SpaceGuid      = s.IdGUID
                AND  bk.BookingStatus IN (1, 4)
                AND  @StartDT          < bk.EndDateTime
                AND  @EndDT            > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC;
END
GO
PRINT 'Step 8 done: WN_Booking_AssignClosestSpace created.';
GO

-- Step 9: WN_Booking_Create
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
    DECLARE @MinCode     INT;
    DECLARE @MaxCode     INT;
    DECLARE @TotalSpaces INT;

    -- Resolve user
    SELECT @UserId = Id, @UserGuid = IdGUID
    FROM   dbo.WN_Users
    WHERE  Email = @Email;

    IF @UserId IS NULL
    BEGIN
        RAISERROR('User not found', 16, 1);
        RETURN;
    END

    -- Resolve config
    SELECT @MinCode = MinCode, @TotalSpaces = TotalSpaces
    FROM   dbo.WN_SpaceConfig
    WHERE  SpaceCategory = @SpaceCategory;

    IF @MinCode IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory', 16, 1);
        RETURN;
    END
    SET @MaxCode = @MinCode + @TotalSpaces - 1;

    -- Lock and find closest available space
    BEGIN TRANSACTION;

    SELECT TOP 1
        @SpaceId           = s.Id,
        @SpaceGuid         = s.IdGUID,
        @AssignedSpaceName = s.Name,
        @AssignedSpaceCode = s.Code
    FROM  dbo.WN_Spaces     s WITH (UPDLOCK)
    JOIN  dbo.WN_SpaceTypes st ON st.IdGUID = s.SpaceTypeId
    WHERE s.Status = 1
      AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND NOT EXISTS (
              SELECT 1
              FROM   dbo.WN_Bookings bk
              WHERE  bk.SpaceGuid      = s.IdGUID
                AND  bk.BookingStatus IN (1, 4)
                AND  @StartDT          < bk.EndDateTime
                AND  @EndDT            > bk.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC;

    IF @SpaceId IS NULL
    BEGIN
        ROLLBACK TRANSACTION;
        RAISERROR('No available space for the requested period', 16, 1);
        RETURN;
    END

    SET @BookingGuid = NEWID();

    INSERT INTO dbo.WN_Bookings
        (IdGUID, UserGuid, SpaceGuid,
         StartDateTime, EndDateTime,
         Notes, TotalAmount, BookingStatus, Status,
         BookingDate, CreatedOn, CreatedBy)
    VALUES
        (@BookingGuid, @UserGuid, @SpaceGuid,
         @StartDT, @EndDT,
         @Notes, @TotalAmount, 1, 1,
         GETUTCDATE(), GETUTCDATE(), @UserGuid);

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
PRINT 'Step 9 done: WN_Booking_Create created.';
GO

PRINT 'ALL DONE - WN Smart Booking Migration v2 completed successfully.';
GO
