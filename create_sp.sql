-- ========================================================
-- WorkNest Database Stored Procedures Migration Script
--
-- This script drops and recreates all WorkNest stored procedures.
-- ========================================================

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Bookings_Cancel
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Bookings_Cancel', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Bookings_Cancel;
GO

CREATE PROCEDURE dbo.WN_Bookings_Cancel
            @BookingId INT,
            @UserId INT
        AS
        BEGIN
            DECLARE @UserGUID UNIQUEIDENTIFIER;
            SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;

            UPDATE dbo.WN_Bookings 
            SET BookingStatus = 2, 
                UpdatedOn = GETDATE(),
                UpdatedBy = @UserGUID
            WHERE Id = @BookingId AND UserGuid = @UserGUID;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Bookings_GetMyList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Bookings_GetMyList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Bookings_GetMyList;
GO

CREATE PROCEDURE dbo.WN_Bookings_GetMyList
            @UserId INT
        AS
        BEGIN
            DECLARE @UserGUID UNIQUEIDENTIFIER;
            SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;

            SELECT 
                b.Id AS id,
                st.Description AS spaceName,
                b.StartDateTime AS startDateTime,
                b.EndDateTime AS endDateTime,
                b.TotalAmount AS totalAmount,
                CASE 
                    WHEN b.BookingStatus = 2 THEN 'Cancelled'
                    WHEN b.BookingStatus = 3 THEN 'Rejected'
                    ELSE 'Confirmed'
                END AS bookingStatus
            FROM dbo.WN_Bookings b
            LEFT JOIN dbo.WN_SpaceTypes st ON b.SpaceGuid = st.IdGUID
            WHERE b.UserGuid = @UserGUID AND b.Status = 1
            ORDER BY b.BookingDate DESC;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Bookings_Insert
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Bookings_Insert', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Bookings_Insert;
GO

CREATE PROCEDURE dbo.WN_Bookings_Insert
            @UserId INT,
            @SpaceId INT,
            @StartDateTime DATETIME,
            @EndDateTime DATETIME,
            @TotalAmount DECIMAL(18,2),
            @Notes NVARCHAR(MAX)
        AS
        BEGIN
            DECLARE @UserGUID UNIQUEIDENTIFIER;
            DECLARE @SpaceGUID UNIQUEIDENTIFIER;

            SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;
            
            -- Resolve Space Type GUID
            SELECT @SpaceGUID = SpaceTypeId FROM dbo.WN_Spaces WHERE Id = @SpaceId;

            INSERT INTO dbo.WN_Bookings 
                (IdGUID, BookingDate, UserGuid, SpaceGuid, StartDateTime, EndDateTime, TotalAmount, BookingStatus, Status, Notes, CreatedOn, CreatedBy)
            VALUES 
                (NEWID(), GETDATE(), @UserGUID, @SpaceGUID, @StartDateTime, @EndDateTime, @TotalAmount, 1, 1, @Notes, GETDATE(), @UserGUID);
                
            SELECT SCOPE_IDENTITY() AS NewId;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_BookTour_Insert
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_BookTour_Insert', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_BookTour_Insert;
GO

CREATE PROCEDURE dbo.WN_BookTour_Insert
            @Name NVARCHAR(255),
            @Email NVARCHAR(256),
            @Message NVARCHAR(100),
            @PhoneNumber NVARCHAR(20),
            @UserId INT = NULL
        AS
        BEGIN
            DECLARE @NewGUID UNIQUEIDENTIFIER = NEWID();
            DECLARE @Now DATETIME = GETDATE();
            
            DECLARE @UserGUID UNIQUEIDENTIFIER = NULL;
            IF @UserId IS NOT NULL
            BEGIN
                SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;
            END

            INSERT INTO dbo.WN_BookTour (IdGUID, Name, Email, Message, PhoneNumber, CreatedOn, CreatedBy)
            VALUES (@NewGUID, @Name, @Email, @Message, @PhoneNumber, @Now, @UserGUID);

            SELECT SCOPE_IDENTITY() AS NewId;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_GalleryImages_GetList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_GalleryImages_GetList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_GalleryImages_GetList;
GO

CREATE PROCEDURE dbo.WN_GalleryImages_GetList
        AS
        BEGIN
            SELECT 
                g.Id AS id,
                g.Title AS title,
                g.Description AS description,
                g.ImageUrl AS imageUrl,
                l.Name AS locationName
            FROM dbo.WN_GalleryImages g
            LEFT JOIN dbo.WN_Locations l ON g.LocationIdGuid = l.IdGUID
            WHERE g.Status = 1;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Locations_GetList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Locations_GetList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Locations_GetList;
GO

CREATE PROCEDURE dbo.WN_Locations_GetList
        AS
        BEGIN
            SELECT 
                [Id] AS id,
                [IdGUID] AS idGuid,
                [Name] AS name,
                [Address] AS address,
                [City] AS city,
                [OpeningTime] AS openingTime,
                [ClosingTime] AS closingTime,
                [Status] AS status
            FROM dbo.WN_Locations WITH (NOLOCK)
            WHERE [Status] = 1;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Payments_GetMyList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Payments_GetMyList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Payments_GetMyList;
GO

CREATE PROCEDURE dbo.WN_Payments_GetMyList
            @UserId INT
        AS
        BEGIN
            DECLARE @UserGUID UNIQUEIDENTIFIER;
            SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;

            SELECT 
                p.Id AS id,
                p.Amount AS amount,
                p.PaymentMethod AS paymentMethod,
                p.PaymentStatus AS paymentStatus,
                p.PaidAt AS paidAt,
                st.Description AS workspaceName,
                p.TransactionRef AS referenceNumber,
                p.TransactionRef AS bankDepositId,
                b.StartDateTime AS start_date,
                b.EndDateTime AS end_date
            FROM dbo.WN_Payments p
            LEFT JOIN dbo.WN_Bookings b ON p.BookingId = b.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON b.SpaceGuid = st.IdGUID
            WHERE p.UserId = @UserGUID
            ORDER BY p.PaidAt DESC;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Payments_Insert
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Payments_Insert', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Payments_Insert;
GO

CREATE PROCEDURE dbo.WN_Payments_Insert
            @UserId INT,
            @BookingId INT,
            @Amount DECIMAL(18,2),
            @PaymentMethod NVARCHAR(100),
            @TransactionRef NVARCHAR(100)
        AS
        BEGIN
            DECLARE @UserGUID UNIQUEIDENTIFIER;
            DECLARE @BookingGUID UNIQUEIDENTIFIER;

            SELECT @UserGUID = IdGUID FROM dbo.WN_Users WHERE Id = @UserId;
            SELECT @BookingGUID = IdGUID FROM dbo.WN_Bookings WHERE Id = @BookingId;

            INSERT INTO dbo.WN_Payments 
                (UserId, BookingId, Amount, Currency, PaymentMethod, PaymentStatus, TransactionRef, PaidAt, CreatedAt)
            VALUES 
                (@UserGUID, @BookingGUID, @Amount, 'PKR', @PaymentMethod, 'Paid', @TransactionRef, GETDATE(), GETDATE());
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_PricingPlans_GetList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_PricingPlans_GetList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_PricingPlans_GetList;
GO

CREATE PROCEDURE dbo.WN_PricingPlans_GetList
        AS
        BEGIN
            SELECT 
                p.Id AS plan_id,
                p.Name AS name,
                p.Price AS price,
                p.Description AS description,
                f.FeatureName AS featureName
            FROM dbo.WN_PricingPlans p
            LEFT JOIN dbo.WN_PlanFeatures f ON p.Id = f.PlanId
            WHERE p.IsActive = 1;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Spaces_GetList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Spaces_GetList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Spaces_GetList;
GO

CREATE PROCEDURE dbo.WN_Spaces_GetList
        AS
        BEGIN
            SELECT 
                s.Id AS id,
                s.Name AS name,
                l.Name AS locationName,
                st.Description AS spaceTypeName,
                st.Capacity AS capacity,
                s.PricePerDay AS pricePerDay,
                s.Amenities AS amenities,
                s.ImageUrl AS imageUrl,
                CASE 
                    WHEN s.Status = 1 THEN 'available'
                    ELSE 'inactive'
                END AS status
            FROM dbo.WN_Spaces s
            LEFT JOIN dbo.WN_Locations l ON s.LocationId = l.IdGUID
            LEFT JOIN dbo.WN_SpaceTypes st ON s.SpaceTypeId = st.IdGUID;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_SpaceTypes_GetList
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_SpaceTypes_GetList', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_SpaceTypes_GetList;
GO

Create PROCEDURE [dbo].[WN_SpaceTypes_GetList] 	
AS
BEGIN
SELECT 
	[Id] 
	,[IdGUID]
	,[Description]
	,[Capacity]
	,[HourlyAllowed]
	,[Status]
	,[CreatedOn]
	,[CreatedBy]
	,[UpdatedOn]
	,[UpdatedBy]
FROM  dbo.WN_SpaceTypes with (nolock) where [Status]=1
END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Users_GetByEmail
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Users_GetByEmail', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Users_GetByEmail;
GO

CREATE PROCEDURE dbo.WN_Users_GetByEmail
            @Email NVARCHAR(256)
        AS
        BEGIN
            SELECT Id FROM dbo.WN_Users WHERE Email = @Email;
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Users_Insert
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Users_Insert', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Users_Insert;
GO

CREATE PROCEDURE dbo.WN_Users_Insert
            @FirstName NVARCHAR(MAX),
            @LastName NVARCHAR(MAX),
            @UserName NVARCHAR(256),
            @Email NVARCHAR(256),
            @PhoneNumber NVARCHAR(MAX)
        AS
        BEGIN
            DECLARE @ExistingId INT;
            SELECT @ExistingId = Id FROM dbo.WN_Users WHERE Email = @Email;

            IF @ExistingId IS NOT NULL
            BEGIN
                UPDATE dbo.WN_Users
                SET Name = LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
                    PhoneNumber = @PhoneNumber,
                    UpdatedOn = GETDATE()
                WHERE Id = @ExistingId;

                SELECT @ExistingId AS NewId;
            END
            ELSE
            BEGIN
                DECLARE @NewId INT;
                BEGIN TRANSACTION;
                
                DECLARE @DoubleCheckId INT;
                SELECT @DoubleCheckId = Id FROM dbo.WN_Users WHERE Email = @Email;

                IF @DoubleCheckId IS NOT NULL
                BEGIN
                    ROLLBACK TRANSACTION;
                    SELECT @DoubleCheckId AS NewId;
                END
                ELSE
                BEGIN
                    INSERT INTO dbo.WN_Users 
                        (IdGUID, Name, CreatedOn, UserName, Email, PhoneNumber)
                    VALUES 
                        (NEWID(), LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))), GETDATE(), @UserName, @Email, @PhoneNumber);
                    
                    SELECT @NewId = SCOPE_IDENTITY();
                    
                    COMMIT TRANSACTION;
                    SELECT @NewId AS NewId;
                END
            END
        END
GO

-- --------------------------------------------------------
-- Stored Procedure: dbo.WN_Users_Update
-- --------------------------------------------------------
IF OBJECT_ID('dbo.WN_Users_Update', 'P') IS NOT NULL
    DROP PROCEDURE dbo.WN_Users_Update;
GO

CREATE PROCEDURE dbo.WN_Users_Update
            @FirstName NVARCHAR(MAX),
            @LastName NVARCHAR(MAX),
            @PhoneNumber NVARCHAR(MAX),
            @Id INT
        AS
        BEGIN
            UPDATE dbo.WN_Users 
            SET Name = LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
                PhoneNumber = @PhoneNumber, 
                UpdatedOn = GETDATE()
            WHERE Id = @Id;
        END
GO

