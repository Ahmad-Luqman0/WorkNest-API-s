-- ============================================================
-- WorkNest Space Configuration & Inventory Migration
-- Run ONCE against the WorkNest database in SSMS
-- ============================================================
-- Creates:
--   1. WN_SpaceConfig  table (admin-editable settings per space category)
--   2. WN_Spaces_GetConfig SP
--   3. WN_Spaces_UpdateConfig SP
--   4. WN_Spaces_GenerateInventory SP  (idempotent — safe to re-run)
--   5. WN_Booking_CheckOverlap SP
--   6. WN_Booking_GetAvailableSpaces SP (replaces WN_GetAvailableSpaces — corrected naming)
--   7. WN_Booking_AssignClosestSpace SP
--   8. WN_Booking_Create SP
-- ============================================================

USE [SAC400]
GO

-- ============================================================
-- SECTION 1: WN_SpaceConfig table
-- ============================================================
-- Stores per-category configuration that admin can change.
-- SpaceCategory values: 'Shared', 'Private', 'Meeting'
-- ============================================================

IF OBJECT_ID('dbo.WN_SpaceConfig', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.WN_SpaceConfig (
        Id              INT IDENTITY(1,1) PRIMARY KEY,
        SpaceCategory   NVARCHAR(20)  NOT NULL,   -- 'Shared' | 'Private' | 'Meeting'
        TotalSpaces     INT           NOT NULL DEFAULT 0,
        CodePrefix      NVARCHAR(5)   NOT NULL,   -- '30', '31', '32'
        MinCode         INT           NOT NULL,   -- e.g. 3001
        DefaultCapacities NVARCHAR(50) NULL,       -- comma-sep: '3,4,5' or '7,8,9,10'
        OpeningTime     NVARCHAR(5)   NOT NULL DEFAULT '08:00',
        ClosingTime     NVARCHAR(5)   NOT NULL DEFAULT '20:00',
        UpdatedOn       DATETIME      NULL,
        UpdatedBy       NVARCHAR(255) NULL
    );
END
GO

-- Seed defaults (idempotent)
IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Shared')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory, TotalSpaces, CodePrefix, MinCode, DefaultCapacities, OpeningTime, ClosingTime)
    VALUES ('Shared', 60, '30', 3001, NULL, '08:00', '20:00');
GO

IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Private')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory, TotalSpaces, CodePrefix, MinCode, DefaultCapacities, OpeningTime, ClosingTime)
    VALUES ('Private', 50, '31', 3101, '3,4,5', '08:00', '20:00');
GO

IF NOT EXISTS (SELECT 1 FROM dbo.WN_SpaceConfig WHERE SpaceCategory = 'Meeting')
    INSERT INTO dbo.WN_SpaceConfig (SpaceCategory, TotalSpaces, CodePrefix, MinCode, DefaultCapacities, OpeningTime, ClosingTime)
    VALUES ('Meeting', 10, '32', 3201, '7,8,9,10', '08:00', '20:00');
GO

PRINT 'WN_SpaceConfig table created and seeded.';
GO

-- ============================================================
-- SECTION 2: WN_Spaces_GetConfig
-- Returns all space category configuration rows.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GetConfig
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        Id, SpaceCategory, TotalSpaces, CodePrefix, MinCode,
        DefaultCapacities, OpeningTime, ClosingTime, UpdatedOn, UpdatedBy
    FROM dbo.WN_SpaceConfig
    ORDER BY Id;
END
GO

-- ============================================================
-- SECTION 3: WN_Spaces_UpdateConfig
-- Admin updates one category row.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_UpdateConfig
    @SpaceCategory      NVARCHAR(20),
    @TotalSpaces        INT,
    @DefaultCapacities  NVARCHAR(50)  = NULL,
    @OpeningTime        NVARCHAR(5)   = NULL,
    @ClosingTime        NVARCHAR(5)   = NULL,
    @AdminEmail         NVARCHAR(255) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_SpaceConfig
    SET TotalSpaces       = @TotalSpaces,
        DefaultCapacities = ISNULL(@DefaultCapacities, DefaultCapacities),
        OpeningTime       = ISNULL(@OpeningTime,       OpeningTime),
        ClosingTime       = ISNULL(@ClosingTime,       ClosingTime),
        UpdatedOn         = GETUTCDATE(),
        UpdatedBy         = @AdminEmail
    WHERE SpaceCategory = @SpaceCategory;

    SELECT @@ROWCOUNT AS AffectedRows;
END
GO

-- ============================================================
-- SECTION 4: WN_Spaces_GenerateInventory
-- Idempotent: creates missing spaces for a category up to TotalSpaces.
-- Needs a SpaceTypeId (from WN_SpaceTypes) and a LocationId (from WN_Locations).
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GenerateInventory
    @SpaceCategory  NVARCHAR(20),   -- 'Shared' | 'Private' | 'Meeting'
    @SpaceTypeId    INT,            -- WN_SpaceTypes.Id
    @LocationId     INT,            -- WN_Locations.Id (numeric)
    @PricePerHour   DECIMAL(10,2) = 0,
    @PricePerDay    DECIMAL(10,2) = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @TotalSpaces INT, @CodePrefix NVARCHAR(5), @MinCode INT;
    DECLARE @LocationGuid UNIQUEIDENTIFIER, @SpaceTypeGuid UNIQUEIDENTIFIER;
    DECLARE @Counter INT, @MaxCode INT, @CodeNum INT, @CodeStr NVARCHAR(10);
    DECLARE @SpaceName NVARCHAR(100);

    SELECT @TotalSpaces = TotalSpaces, @CodePrefix = CodePrefix, @MinCode = MinCode
    FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;

    IF @TotalSpaces IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory: %s', 16, 1, @SpaceCategory);
        RETURN;
    END

    SELECT @LocationGuid  = IdGUID FROM dbo.WN_Locations  WHERE Id = @LocationId  AND Status = 1;
    SELECT @SpaceTypeGuid = IdGUID FROM dbo.WN_SpaceTypes  WHERE Id = @SpaceTypeId AND Status = 1;

    IF @LocationGuid IS NULL OR @SpaceTypeGuid IS NULL
    BEGIN
        RAISERROR('Invalid LocationId or SpaceTypeId', 16, 1);
        RETURN;
    END

    SET @MaxCode = @MinCode + @TotalSpaces - 1;
    SET @Counter = @MinCode;

    WHILE @Counter <= @MaxCode
    BEGIN
        SET @CodeStr  = CAST(@Counter AS NVARCHAR(10));
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

    -- Deactivate spaces that exceed TotalSpaces
    UPDATE dbo.WN_Spaces
    SET Status = 0
    WHERE SpaceTypeId = @SpaceTypeGuid
      AND TRY_CAST(Code AS INT) IS NOT NULL
      AND TRY_CAST(Code AS INT) > @MaxCode
      AND TRY_CAST(Code AS INT) >= @MinCode;

    SELECT @@ROWCOUNT AS DeactivatedCount, @TotalSpaces AS TotalConfigured;
END
GO

-- ============================================================
-- SECTION 5: WN_Booking_CheckOverlap
-- Returns 1 if the given space is occupied in the time window.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Booking_CheckOverlap
    @SpaceId        INT,
    @StartDateTime  DATETIME,
    @EndDateTime    DATETIME,
    @ExcludeBookingId INT = NULL    -- exclude current booking when editing
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM dbo.WN_Bookings
        WHERE SpaceId = @SpaceId
          AND BookingStatus IN (1, 4)
          AND (@ExcludeBookingId IS NULL OR Id != @ExcludeBookingId)
          AND @StartDateTime < EndDateTime
          AND @EndDateTime   > StartDateTime
    )
        SELECT 1 AS IsOverlapping;
    ELSE
        SELECT 0 AS IsOverlapping;
END
GO

-- ============================================================
-- SECTION 6: WN_Booking_GetAvailableSpaces
-- Returns available spaces ordered by numeric code (closest first).
-- Replaces WN_GetAvailableSpaces with corrected JOIN logic.
-- Supports optional capacity filter for Private/Meeting rooms.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Booking_GetAvailableSpaces
    @SpaceCategory  NVARCHAR(20),   -- 'Shared' | 'Private' | 'Meeting'
    @StartDateTime  DATETIME,
    @EndDateTime    DATETIME,
    @Capacity       INT = NULL      -- filter by min capacity (for Private/Meeting)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CodePrefix NVARCHAR(5), @MinCode INT, @MaxCode INT, @TotalSpaces INT;
    SELECT @CodePrefix = CodePrefix, @MinCode = MinCode, @TotalSpaces = TotalSpaces
    FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;

    IF @CodePrefix IS NULL
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
        st.Description  AS SpaceType,
        st.Capacity     AS Capacity,
        l.Name          AS LocationName,
        TRY_CAST(s.Code AS INT) AS CodeNumber
    FROM dbo.WN_Spaces s
    INNER JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
    INNER JOIN dbo.WN_Locations  l  ON s.LocationId  = l.IdGUID
    WHERE s.Status = 1
      AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND s.Id NOT IN (
            SELECT DISTINCT b.SpaceId
            FROM dbo.WN_Bookings b
            WHERE b.BookingStatus IN (1, 4)
              AND b.SpaceId IS NOT NULL
              AND @StartDateTime < b.EndDateTime
              AND @EndDateTime   > b.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC;
END
GO

-- ============================================================
-- SECTION 7: WN_Booking_AssignClosestSpace
-- Returns the single lowest-numbered available space.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Booking_AssignClosestSpace
    @SpaceCategory  NVARCHAR(20),
    @StartDateTime  DATETIME,
    @EndDateTime    DATETIME,
    @Capacity       INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CodePrefix NVARCHAR(5), @MinCode INT, @MaxCode INT, @TotalSpaces INT;
    SELECT @CodePrefix = CodePrefix, @MinCode = MinCode, @TotalSpaces = TotalSpaces
    FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;

    IF @CodePrefix IS NULL
    BEGIN
        RAISERROR('Unknown SpaceCategory', 16, 1);
        RETURN;
    END

    SET @MaxCode = @MinCode + @TotalSpaces - 1;

    SELECT TOP 1
        s.Id, s.IdGUID, s.Name, s.Code,
        st.Capacity, l.Name AS LocationName
    FROM dbo.WN_Spaces s
    INNER JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
    INNER JOIN dbo.WN_Locations  l  ON s.LocationId  = l.IdGUID
    WHERE s.Status = 1
      AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
      AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
      AND s.Id NOT IN (
            SELECT DISTINCT b.SpaceId
            FROM dbo.WN_Bookings b
            WHERE b.BookingStatus IN (1, 4)
              AND b.SpaceId IS NOT NULL
              AND @StartDateTime < b.EndDateTime
              AND @EndDateTime   > b.StartDateTime
          )
    ORDER BY TRY_CAST(s.Code AS INT) ASC;
END
GO

-- ============================================================
-- SECTION 8: WN_Booking_Create
-- Creates a booking after assigning the closest space.
-- Auto-assigns if @SpaceId = NULL.
-- ============================================================
CREATE OR ALTER PROCEDURE dbo.WN_Booking_Create
    @Email          NVARCHAR(255),
    @SpaceCategory  NVARCHAR(20),
    @StartDateTime  DATETIME,
    @EndDateTime    DATETIME,
    @Notes          NVARCHAR(MAX) = '',
    @TotalAmount    DECIMAL(10,2) = 0,
    @PaymentMethod  NVARCHAR(50)  = NULL,
    @PaymentRef     NVARCHAR(100) = NULL,
    @Capacity       INT = NULL,
    @BookingId      INT OUTPUT,
    @BookingGuid    UNIQUEIDENTIFIER OUTPUT,
    @AssignedSpaceId   INT OUTPUT,
    @AssignedSpaceName NVARCHAR(255) OUTPUT,
    @AssignedSpaceCode NVARCHAR(20)  OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRANSACTION;
    BEGIN TRY
        DECLARE @UserId INT, @UserGuid UNIQUEIDENTIFIER;
        DECLARE @SpaceId INT, @SpaceGuid UNIQUEIDENTIFIER;
        DECLARE @CodePrefix NVARCHAR(5), @MinCode INT, @MaxCode INT, @TotalSpaces INT;

        -- Resolve user
        SELECT @UserId = Id, @UserGuid = IdGUID
        FROM dbo.WN_Users
        WHERE Email = @Email AND ISNULL(Status, 1) = 1;

        IF @UserId IS NULL
        BEGIN
            RAISERROR('User not found or inactive', 16, 1);
            RETURN;
        END

        -- Config for this category
        SELECT @CodePrefix = CodePrefix, @MinCode = MinCode, @TotalSpaces = TotalSpaces
        FROM dbo.WN_SpaceConfig WHERE SpaceCategory = @SpaceCategory;

        IF @CodePrefix IS NULL
        BEGIN
            RAISERROR('Unknown SpaceCategory', 16, 1);
            RETURN;
        END

        SET @MaxCode = @MinCode + @TotalSpaces - 1;

        -- Assign closest available space (with UPDLOCK to prevent race condition)
        SELECT TOP 1
            @SpaceId   = s.Id,
            @SpaceGuid = s.IdGUID,
            @AssignedSpaceName = s.Name,
            @AssignedSpaceCode = s.Code
        FROM dbo.WN_Spaces s WITH (UPDLOCK)
        INNER JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID
        WHERE s.Status = 1
          AND TRY_CAST(s.Code AS INT) BETWEEN @MinCode AND @MaxCode
          AND (@Capacity IS NULL OR st.Capacity >= @Capacity)
          AND s.Id NOT IN (
                SELECT DISTINCT b.SpaceId
                FROM dbo.WN_Bookings b
                WHERE b.BookingStatus IN (1, 4)
                  AND b.SpaceId IS NOT NULL
                  AND @StartDateTime < b.EndDateTime
                  AND @EndDateTime   > b.StartDateTime
              )
        ORDER BY TRY_CAST(s.Code AS INT) ASC;

        IF @SpaceId IS NULL
        BEGIN
            RAISERROR('No available space for the requested period and capacity', 16, 1);
            RETURN;
        END

        -- Create booking
        SET @BookingGuid = NEWID();

        INSERT INTO dbo.WN_Bookings
            (IdGUID, UserGuid, SpaceId, SpaceGuid, StartDateTime, EndDateTime,
             Notes, TotalAmount, BookingStatus, Status, BookingDate, CreatedOn, CreatedBy)
        VALUES
            (@BookingGuid, @UserGuid, @SpaceId, @SpaceGuid, @StartDateTime, @EndDateTime,
             @Notes, @TotalAmount, 1, 1, GETUTCDATE(), GETUTCDATE(), @UserGuid);

        SET @BookingId       = SCOPE_IDENTITY();
        SET @AssignedSpaceId = @SpaceId;

        -- Create payment record if method provided
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
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        DECLARE @Msg NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@Msg, ERROR_SEVERITY(), ERROR_STATE());
    END CATCH
END
GO

PRINT 'Space configuration migration completed successfully.';
GO
