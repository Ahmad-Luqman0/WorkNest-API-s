-- ============================================================
-- WorkNest Auto-Assignment Booking System Stored Procedures
-- ============================================================
-- These stored procedures replace inline queries for:
-- - Auto-assignment booking logic with space naming conventions
-- - Real-time availability checking and updates
-- - Transaction-safe booking operations
-- - Admin reassignment functionality

USE [WorkNest]
GO

-- ============================================================
-- 1. Get Available Spaces for Auto-Assignment
-- ============================================================
-- Implements space naming convention: 30X (Private Rooms), 31X (Shared), 32X (Meeting)
-- Returns available spaces with priority ordering for assignment

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
    
    -- Get space type ID
    SELECT @SpaceTypeId = Id 
    FROM WN_SpaceTypes 
    WHERE Description = @SpaceType AND Status = 1;
    
    IF @SpaceTypeId IS NULL
    BEGIN
        RAISERROR('Invalid space type', 16, 1);
        RETURN;
    END
    
    -- Get available spaces with naming convention priority
    SELECT 
        s.Id,
        s.IdGUID,
        s.Name,
        s.Code,
        s.PricePerDay,
        s.PricePerHour,
        st.Description AS SpaceType,
        l.Name AS LocationName,
        -- Priority based on naming convention
        CASE 
            WHEN @SpaceType LIKE '%Private%' AND s.Code LIKE '30%%' THEN 1
            WHEN @SpaceType LIKE '%Shared%' AND s.Code LIKE '31%%' THEN 1  
            WHEN @SpaceType LIKE '%Meeting%' AND s.Code LIKE '32%%' THEN 1
            ELSE 2
        END AS Priority,
        -- Extract numeric part for ordering within same prefix
        CASE 
            WHEN ISNUMERIC(SUBSTRING(s.Code, 3, LEN(s.Code)-2)) = 1 
            THEN CAST(SUBSTRING(s.Code, 3, LEN(s.Code)-2) AS INT)
            ELSE 999
        END AS CodeNumber
    FROM WN_Spaces s
    INNER JOIN WN_SpaceTypes st ON s.SpaceTypeId = st.Id
    INNER JOIN WN_Locations l ON s.LocationId = l.Id
    WHERE s.SpaceTypeId = @SpaceTypeId 
        AND s.Status = 1
        AND s.Id NOT IN (
            -- Exclude spaces with conflicting bookings
            SELECT DISTINCT b.SpaceId
            FROM WN_Bookings b
            WHERE b.BookingStatus IN (1, 4) -- Confirmed or Completed
                AND (
                    (@StartDateTime >= b.StartDateTime AND @StartDateTime < b.EndDateTime) OR
                    (@EndDateTime > b.StartDateTime AND @EndDateTime <= b.EndDateTime) OR
                    (@StartDateTime <= b.StartDateTime AND @EndDateTime >= b.EndDateTime)
                )
        )
    ORDER BY Priority ASC, CodeNumber ASC;
END
GO

-- ============================================================
-- 2. Create Booking with Auto-Assignment
-- ============================================================
-- Transaction-safe booking creation with automatic space assignment

IF OBJECT_ID('WN_CreateBookingWithAutoAssignment', 'P') IS NOT NULL
    DROP PROCEDURE WN_CreateBookingWithAutoAssignment
GO

CREATE PROCEDURE WN_CreateBookingWithAutoAssignment
    @Email NVARCHAR(255),
    @SpaceType NVARCHAR(100),
    @StartDateTime DATETIME,
    @EndDateTime DATETIME,
    @notes NVARCHAR(MAX) = '',
    @totalAmount DECIMAL(10,2) = 0,
    @paymentMethod NVARCHAR(50) = NULL,
    @paymentRef NVARCHAR(100) = NULL,
    @bookingId INT OUTPUT,
    @bookingGuid UNIQUEIDENTIFIER OUTPUT,
    @AssignedSpaceId INT OUTPUT,
    @assignedSpaceName NVARCHAR(255) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRANSACTION;
    
    BEGIN TRY
        DECLARE @UserId INT, @userGuid UNIQUEIDENTIFIER;
        DECLARE @SpaceId INT, @SpaceGuid UNIQUEIDENTIFIER;
        
        -- Get user ID
        SELECT @UserId = Id, @userGuid = IdGUID 
        FROM WN_Users 
        WHERE Email = @Email AND Status = 1;
        
        IF @UserId IS NULL
        BEGIN
            RAISERROR('User not found or inactive', 16, 1);
            RETURN;
        END
        
        -- Get next available space using auto-assignment logic
        SELECT TOP 1 
            @SpaceId = Id,
            @SpaceGuid = IdGUID,
            @assignedSpaceName = Name
        FROM (
            SELECT 
                s.Id,
                s.IdGUID,
                s.Name,
                -- Priority based on naming convention
                CASE 
                    WHEN @SpaceType LIKE '%Private%' AND s.Code LIKE '30%' THEN 1
                    WHEN @SpaceType LIKE '%Shared%' AND s.Code LIKE '31%' THEN 1  
                    WHEN @SpaceType LIKE '%Meeting%' AND s.Code LIKE '32%' THEN 1
                    ELSE 2
                END AS Priority,
                -- Extract numeric part for ordering
                CASE 
                    WHEN ISNUMERIC(SUBSTRING(s.Code, 3, LEN(s.Code)-2)) = 1 
                    THEN CAST(SUBSTRING(s.Code, 3, LEN(s.Code)-2) AS INT)
                    ELSE 999
                END AS CodeNumber
            FROM WN_Spaces s
            INNER JOIN WN_SpaceTypes st ON s.SpaceTypeId = st.Id
            WHERE st.Description = @SpaceType 
                AND s.Status = 1
                AND s.Id NOT IN (
                    SELECT DISTINCT b.SpaceId
                    FROM WN_Bookings b WITH (UPDLOCK)
                    WHERE b.BookingStatus IN (1, 4)
                        AND (
                            (@StartDateTime >= b.StartDateTime AND @StartDateTime < b.EndDateTime) OR
                            (@EndDateTime > b.StartDateTime AND @EndDateTime <= b.EndDateTime) OR
                            (@StartDateTime <= b.StartDateTime AND @EndDateTime >= b.EndDateTime)
                        )
                )
        ) AS AvailableSpaces
        ORDER BY Priority ASC, CodeNumber ASC;
        
        IF @SpaceId IS NULL
        BEGIN
            RAISERROR('No available spaces for the requested time period', 16, 1);
            RETURN;
        END
        
        -- Create booking
        SET @bookingGuid = NEWID();
        
        INSERT INTO WN_Bookings (
            IdGUID, UserGuid, SpaceId, SpaceGuid, StartDateTime, EndDateTime,
            Notes, TotalAmount, BookingStatus, CreatedOn, UpdatedOn
        ) VALUES (
            @bookingGuid, @userGuid, @SpaceId, @SpaceGuid, @StartDateTime, @EndDateTime,
            @notes, @totalAmount, 1, GETUTCDATE(), GETUTCDATE()
        );
        
        SET @bookingId = SCOPE_IDENTITY();
        SET @AssignedSpaceId = @SpaceId;
        
        -- Create payment record if provided
        IF @paymentMethod IS NOT NULL AND @totalAmount > 0
        BEGIN
            INSERT INTO WN_Payments (
                IdGUID, UserId, BookingId, Amount, PaymentMethod, 
                TransactionRef, PaymentStatus, CreatedOn
            ) VALUES (
                NEWID(), @UserId, @bookingId, @totalAmount, @paymentMethod,
                @paymentRef, 'Pending', GETUTCDATE()
            );
        END
        
        COMMIT TRANSACTION;
        
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrorState INT = ERROR_STATE();
        
        RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO

-- ============================================================
-- 3. Get Availability Counts by Space Type
-- ============================================================
-- Real-time availability counts for live updates

IF OBJECT_ID('WN_GetAvailabilityCounts', 'P') IS NOT NULL
    DROP PROCEDURE WN_GetAvailabilityCounts
GO

CREATE PROCEDURE WN_GetAvailabilityCounts
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        st.Description AS spaceType,
        COUNT(s.Id) AS totalSpaces,
        COUNT(s.Id) - ISNULL(booked.BookedCount, 0) AS availableSpaces,
        ISNULL(booked.BookedCount, 0) AS bookedSpaces
    FROM WN_SpaceTypes st
    LEFT JOIN WN_Spaces s ON st.Id = s.SpaceTypeId AND s.Status = 1
    LEFT JOIN (
        SELECT 
            s.SpaceTypeId,
            COUNT(DISTINCT s.Id) AS BookedCount
        FROM WN_Spaces s
        INNER JOIN WN_Bookings b ON s.Id = b.SpaceId
        WHERE b.BookingStatus IN (1, 4) -- Confirmed or Completed
            AND b.StartDateTime <= GETUTCDATE()
            AND b.EndDateTime >= GETUTCDATE()
        GROUP BY s.SpaceTypeId
    ) booked ON st.Id = booked.SpaceTypeId
    WHERE st.Status = 1
    GROUP BY st.Description, booked.BookedCount
    ORDER BY st.Description;
END
GO

-- ============================================================
-- 4. Get Available Spaces by Type with Time Filter
-- ============================================================
-- For booking page availability checking

IF OBJECT_ID('WN_GetAvailableSpacesByType', 'P') IS NOT NULL
    DROP PROCEDURE WN_GetAvailableSpacesByType
GO

CREATE PROCEDURE WN_GetAvailableSpacesByType
    @SpaceType NVARCHAR(100),
    @StartDateTime DATETIME = NULL,
    @EndDateTime DATETIME = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @SpaceTypeId INT;
    
    SELECT @SpaceTypeId = Id 
    FROM WN_SpaceTypes 
    WHERE Description = @SpaceType AND Status = 1;
    
    IF @SpaceTypeId IS NULL
    BEGIN
        SELECT 0 AS totalSpaces, 0 AS availableSpaces;
        RETURN;
    END
    
    -- If no time filter, return current availability
    IF @startDateTime IS NULL OR @endDateTime IS NULL
    BEGIN
        SELECT 
            COUNT(s.Id) AS totalSpaces,
            COUNT(s.Id) - ISNULL(booked.BookedCount, 0) AS availableSpaces
        FROM WN_Spaces s
        LEFT JOIN (
            SELECT 
                s2.SpaceTypeId,
                COUNT(DISTINCT s2.Id) AS BookedCount
            FROM WN_Spaces s2
            INNER JOIN WN_Bookings b ON s2.Id = b.SpaceId
            WHERE b.BookingStatus IN (1, 4)
                AND b.StartDateTime <= GETUTCDATE()
                AND b.EndDateTime >= GETUTCDATE()
                AND s2.SpaceTypeId = @spaceTypeId
        ) booked ON 1 = 1
        WHERE s.SpaceTypeId = @spaceTypeId AND s.Status = 1;
        RETURN;
    END
    
    -- Return availability for specific time period
    SELECT 
        COUNT(s.Id) AS totalSpaces,
        COUNT(s.Id) - COUNT(b.SpaceId) AS availableSpaces
    FROM WN_Spaces s
    LEFT JOIN WN_Bookings b ON s.Id = b.SpaceId 
        AND b.BookingStatus IN (1, 4)
        AND (
            (@startDateTime >= b.StartDateTime AND @startDateTime < b.EndDateTime) OR
            (@endDateTime > b.StartDateTime AND @endDateTime <= b.EndDateTime) OR
            (@startDateTime <= b.StartDateTime AND @endDateTime >= b.EndDateTime)
        )
    WHERE s.SpaceTypeId = @spaceTypeId AND s.Status = 1;
END
GO

-- ============================================================
-- 5. Reassign Booking to Different Space
-- ============================================================
-- Admin functionality for booking reassignment

IF OBJECT_ID('WN_ReassignBooking', 'P') IS NOT NULL
    DROP PROCEDURE WN_ReassignBooking
GO

CREATE PROCEDURE WN_ReassignBooking
    @bookingId INT,
    @newSpaceId INT,
    @adminUserEmail NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRANSACTION;
    
    BEGIN TRY
        DECLARE @oldSpaceId INT, @spaceGuid UNIQUEIDENTIFIER;
        DECLARE @StartDateTime DATETIME, @EndDateTime DATETIME;
        DECLARE @BookingGuid UNIQUEIDENTIFIER;
        
        -- Validate admin user
        IF NOT EXISTS (
            SELECT 1 FROM WN_Users 
            WHERE Email = @adminUserEmail AND RoleId IN (1, 2) -- Admin roles
        )
        BEGIN
            RAISERROR('Unauthorized: Admin access required', 16, 1);
            RETURN;
        END
        
        -- Get current booking details
        SELECT 
            @oldSpaceId = SpaceId,
            @StartDateTime = StartDateTime,
            @EndDateTime = EndDateTime,
            @BookingGuid = IdGUID
        FROM WN_Bookings 
        WHERE Id = @BookingId AND BookingStatus = 1; -- Only confirmed bookings
        
        IF @oldSpaceId IS NULL
        BEGIN
            RAISERROR('Booking not found or not in confirmed status', 16, 1);
            RETURN;
        END
        
        -- Check if new space is available
        IF EXISTS (
            SELECT 1 FROM WN_Bookings b
            WHERE b.SpaceId = @newSpaceId 
                AND b.BookingStatus IN (1, 4)
                AND b.Id != @BookingId -- Exclude current booking
                AND (
                    (@StartDateTime >= b.StartDateTime AND @StartDateTime < b.EndDateTime) OR
                    (@EndDateTime > b.StartDateTime AND @EndDateTime <= b.EndDateTime) OR
                    (@StartDateTime <= b.StartDateTime AND @EndDateTime >= b.EndDateTime)
                )
        )
        BEGIN
            RAISERROR('Target space is not available for the booking period', 16, 1);
            RETURN;
        END
        
        -- Get new space GUID
        SELECT @spaceGuid = IdGUID 
        FROM WN_Spaces 
        WHERE Id = @newSpaceId AND Status = 1;
        
        IF @spaceGuid IS NULL
        BEGIN
            RAISERROR('Invalid target space', 16, 1);
            RETURN;
        END
        
        -- Update booking with new space
        UPDATE WN_Bookings 
        SET SpaceId = @newSpaceId,
            SpaceGuid = @spaceGuid,
            UpdatedOn = GETUTCDATE(),
            Notes = ISNULL(Notes, '') + CHAR(13) + CHAR(10) + 
                   'Reassigned by admin on ' + CONVERT(NVARCHAR, GETUTCDATE(), 121)
        WHERE Id = @bookingId;
        
        COMMIT TRANSACTION;
        
        -- Return updated booking info
        SELECT 
            b.IdGUID AS bookingId,
            s.Name AS newSpaceName,
            s.Code AS newSpaceCode,
            'Success' AS status
        FROM WN_Bookings b
        INNER JOIN WN_Spaces s ON b.SpaceId = s.Id
        WHERE b.Id = @bookingId;
        
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrorState INT = ERROR_STATE();
        
        RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState);
    END CATCH
END
GO

-- ============================================================
-- 6. Get Available Spaces for Reassignment
-- ============================================================
-- Get spaces available for admin reassignment (excluding current booking)

IF OBJECT_ID('WN_GetAvailableSpacesForReassignment', 'P') IS NOT NULL
    DROP PROCEDURE WN_GetAvailableSpacesForReassignment
GO

CREATE PROCEDURE WN_GetAvailableSpacesForReassignment
    @spaceType NVARCHAR(100),
    @startDateTime DATETIME,
    @endDateTime DATETIME,
    @excludeBookingId INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @spaceTypeId INT;
    
    SELECT @spaceTypeId = Id 
    FROM WN_SpaceTypes 
    WHERE Description = @spaceType AND Status = 1;
    
    SELECT 
        s.Id,
        s.IdGUID,
        s.Name,
        s.Code,
        s.Description,
        l.Name AS LocationName
    FROM WN_Spaces s
    INNER JOIN WN_SpaceTypes st ON s.SpaceTypeId = st.Id
    INNER JOIN WN_Locations l ON s.LocationId = l.Id
    WHERE s.SpaceTypeId = @spaceTypeId 
        AND s.Status = 1
        AND s.Id NOT IN (
            SELECT DISTINCT b.SpaceId
            FROM WN_Bookings b
            WHERE b.BookingStatus IN (1, 4) -- Confirmed or Completed
                AND (@excludeBookingId IS NULL OR b.Id != @excludeBookingId)
                AND (
                    (@startDateTime >= b.StartDateTime AND @startDateTime < b.EndDateTime) OR
                    (@endDateTime > b.StartDateTime AND @endDateTime <= b.EndDateTime) OR
                    (@startDateTime <= b.StartDateTime AND @endDateTime >= b.EndDateTime)
                )
        )
    ORDER BY 
        CASE 
            WHEN @spaceType LIKE '%Private%' AND s.Code LIKE '30%' THEN 1
            WHEN @spaceType LIKE '%Shared%' AND s.Code LIKE '31%' THEN 1  
            WHEN @spaceType LIKE '%Meeting%' AND s.Code LIKE '32%' THEN 1
            ELSE 2
        END,
        s.Code;
END
GO

-- ============================================================
-- 7. Get Booking Calendar Data
-- ============================================================
-- Calendar view for admin booking management

IF OBJECT_ID('WN_GetBookingCalendar', 'P') IS NOT NULL
    DROP PROCEDURE WN_GetBookingCalendar
GO

CREATE PROCEDURE WN_GetBookingCalendar
    @spaceId INT,
    @year INT,
    @month INT
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        b.IdGUID AS bookingId,
        b.StartDateTime,
        b.EndDateTime,
        CONVERT(VARCHAR, b.StartDateTime, 23) AS startDate,
        CONVERT(VARCHAR, b.EndDateTime, 23) AS endDate,
        u.Email AS userEmail,
        u.Name AS userName,
        CASE b.BookingStatus 
            WHEN 1 THEN 'Confirmed'
            WHEN 2 THEN 'Cancelled' 
            WHEN 3 THEN 'Rejected'
            WHEN 4 THEN 'Completed'
            ELSE 'Unknown'
        END AS status,
        b.TotalAmount
    FROM WN_Bookings b
    INNER JOIN WN_Spaces s ON b.SpaceId = s.Id
    LEFT JOIN WN_Users u ON b.UserGuid = u.IdGUID
    WHERE s.Id = @spaceId 
        AND b.BookingStatus != 2 -- Exclude cancelled
        AND YEAR(b.StartDateTime) = @year 
        AND MONTH(b.StartDateTime) = @month
    ORDER BY b.StartDateTime;
END
GO

-- ============================================================
-- 8. Validate Space Assignment (Utility)
-- ============================================================
-- Validates space naming convention and assignment rules

IF OBJECT_ID('WN_ValidateSpaceAssignment', 'P') IS NOT NULL
    DROP PROCEDURE WN_ValidateSpaceAssignment
GO

CREATE PROCEDURE WN_ValidateSpaceAssignment
    @spaceType NVARCHAR(100),
    @spaceCode NVARCHAR(50),
    @isValid BIT OUTPUT,
    @message NVARCHAR(255) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    SET @isValid = 0;
    SET @message = 'Invalid space assignment';
    
    -- Validate naming convention
    IF @spaceType LIKE '%Private%' AND @spaceCode LIKE '30[0-9]'
    BEGIN
        SET @isValid = 1;
        SET @message = 'Valid private room assignment';
    END
    ELSE IF @spaceType LIKE '%Shared%' AND @spaceCode LIKE '31[0-9]'
    BEGIN
        SET @isValid = 1;
        SET @message = 'Valid shared space assignment';
    END
    ELSE IF @spaceType LIKE '%Meeting%' AND @spaceCode LIKE '32[0-9]'
    BEGIN
        SET @isValid = 1;
        SET @message = 'Valid meeting room assignment';
    END
    ELSE
    BEGIN
        SET @message = 'Space code does not match naming convention for ' + @spaceType;
    END
END
GO

-- ============================================================
-- Grant Permissions
-- ============================================================
-- Grant execute permissions to application user

GRANT EXECUTE ON WN_GetAvailableSpaces TO [WorkNestApp]
GRANT EXECUTE ON WN_CreateBookingWithAutoAssignment TO [WorkNestApp]
GRANT EXECUTE ON WN_GetAvailabilityCounts TO [WorkNestApp] 
GRANT EXECUTE ON WN_GetAvailableSpacesByType TO [WorkNestApp]
GRANT EXECUTE ON WN_ReassignBooking TO [WorkNestApp]
GRANT EXECUTE ON WN_GetAvailableSpacesForReassignment TO [WorkNestApp]
GRANT EXECUTE ON WN_GetBookingCalendar TO [WorkNestApp]
GRANT EXECUTE ON WN_ValidateSpaceAssignment TO [WorkNestApp]

PRINT 'Auto-Assignment Booking System Stored Procedures Created Successfully!'