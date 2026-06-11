-- Apply GUID return and NOLOCK migration for WorkNest stored procedures
-- Run this script in SSMS (use a development DB first)
SET NOCOUNT ON;

/*
Notes:
- Adds IdGUID AS idGuid where appropriate
- Returns NewIdGuid for INSERT procedures where a GUID is generated
- Adds WITH (NOLOCK) on table scans and joins to reduce blocking in reporting queries
- Review and test before applying to production
*/

GO

-- Bookings: Get list by user id (returns idGuid)
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_GetListByUserId
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    SELECT
        b.IdGUID AS idGuid,
        b.Id AS id,
        st.Description AS spaceName,
        b.StartDateTime AS startDateTime,
        b.EndDateTime AS endDateTime,
        b.TotalAmount AS totalAmount,
        b.Notes AS notes,
        b.BookingDate AS createdAt,
        CASE
            WHEN b.BookingStatus = 2 THEN 'Cancelled'
            WHEN b.BookingStatus = 3 THEN 'Rejected'
            WHEN b.BookingStatus = 1 THEN 'Pending'
            ELSE 'Confirmed'
        END AS bookingStatus
    FROM dbo.WN_Bookings b WITH (NOLOCK)
    LEFT JOIN dbo.WN_SpaceTypes st WITH (NOLOCK) ON b.SpaceGuid = st.IdGUID
    WHERE b.UserGuid = @UserGUID AND b.Status = 1
    ORDER BY b.BookingDate DESC;
END
GO

-- Bookings: Insert (returns numeric id and GUID)
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_Insert
    @UserId INT,
    @SpaceId INT,
    @StartDateTime DATETIME,
    @EndDateTime DATETIME,
    @TotalAmount DECIMAL(18,2),
    @Notes NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    DECLARE @SpaceGUID UNIQUEIDENTIFIER;
    DECLARE @NewBookingGUID UNIQUEIDENTIFIER = NEWID();

    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;
    -- Resolve space GUID from spaces table (assumes SpaceTypeId is stored as GUID in table)
    SELECT @SpaceGUID = IdGUID FROM dbo.WN_Spaces WITH (NOLOCK) WHERE Id = @SpaceId;

    INSERT INTO dbo.WN_Bookings
        (IdGUID, BookingDate, UserGuid, SpaceGuid, StartDateTime, EndDateTime, TotalAmount, BookingStatus, Status, Notes, CreatedOn, CreatedBy)
    VALUES
        (@NewBookingGUID, GETDATE(), @UserGUID, @SpaceGUID, @StartDateTime, @EndDateTime, @TotalAmount, 1, 1, @Notes, GETDATE(), @UserGUID);

    SELECT SCOPE_IDENTITY() AS NewId, @NewBookingGUID AS NewIdGuid;
END
GO

-- Book Tour: insert and return GUID
CREATE OR ALTER PROCEDURE dbo.WN_BookTour_Insert
    @Name NVARCHAR(255),
    @Email NVARCHAR(256),
    @Message NVARCHAR(100),
    @PhoneNumber NVARCHAR(20),
    @UserId INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @NewGUID UNIQUEIDENTIFIER = NEWID();
    DECLARE @Now DATETIME = GETDATE();
    DECLARE @UserGUID UNIQUEIDENTIFIER = NULL;
    IF @UserId IS NOT NULL
    BEGIN
        SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;
    END

    INSERT INTO dbo.WN_BookTour (IdGUID, Name, Email, Message, PhoneNumber, CreatedOn, CreatedBy)
    VALUES (@NewGUID, @Name, @Email, @Message, @PhoneNumber, @Now, @UserGUID);

    SELECT SCOPE_IDENTITY() AS NewId, @NewGUID AS NewIdGuid;
END
GO

-- Gallery images: include GUIDs
CREATE OR ALTER PROCEDURE dbo.WN_GalleryImages_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        g.IdGUID AS idGuid,
        g.Id AS id,
        g.Title AS title,
        g.Description AS description,
        g.ImageUrl AS imageUrl,
        g.LocationIdGuid AS locationIdGuid,
        l.IdGUID AS locationIdGuid_from_location,
        l.Name AS locationName
    FROM dbo.WN_GalleryImages g WITH (NOLOCK)
    LEFT JOIN dbo.WN_Locations l WITH (NOLOCK) ON g.LocationIdGuid = l.IdGUID
    WHERE g.Status = 1;
END
GO

-- Locations: ensure NOLOCK already present in original; keep return of IdGUID
CREATE OR ALTER PROCEDURE dbo.WN_Locations_GetList
AS
BEGIN
    SET NOCOUNT ON;
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

-- Payments: get my payments (include payment GUID)
CREATE OR ALTER PROCEDURE dbo.WN_Payments_GetMyList
    @UserId INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;

    SELECT
        p.IdGUID AS idGuid,
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
    FROM dbo.WN_Payments p WITH (NOLOCK)
    LEFT JOIN dbo.WN_Bookings b WITH (NOLOCK) ON p.BookingId = b.IdGUID
    LEFT JOIN dbo.WN_SpaceTypes st WITH (NOLOCK) ON b.SpaceGuid = st.IdGUID
    WHERE p.UserId = @UserGUID
    ORDER BY p.PaidAt DESC;
END
GO

-- Payments: insert and return new id and GUID
CREATE OR ALTER PROCEDURE dbo.WN_Payments_Insert
    @UserId INT,
    @BookingId INT,
    @Amount DECIMAL(18,2),
    @PaymentMethod NVARCHAR(100),
    @TransactionRef NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @UserGUID UNIQUEIDENTIFIER;
    DECLARE @BookingGUID UNIQUEIDENTIFIER;

    SELECT @UserGUID = IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Id = @UserId;
    SELECT @BookingGUID = IdGUID FROM dbo.WN_Bookings WITH (NOLOCK) WHERE Id = @BookingId;

    INSERT INTO dbo.WN_Payments
        (UserId, BookingId, Amount, Currency, PaymentMethod, PaymentStatus, TransactionRef, PaidAt, CreatedAt)
    VALUES
        (@UserGUID, @BookingGUID, @Amount, 'PKR', @PaymentMethod, 'Paid', @TransactionRef, GETDATE(), GETDATE());

    SELECT SCOPE_IDENTITY() AS NewId, (SELECT IdGUID FROM dbo.WN_Payments WITH (NOLOCK) WHERE Id = SCOPE_IDENTITY()) AS NewIdGuid;
END
GO

-- Pricing plans: include GUID if present
CREATE OR ALTER PROCEDURE dbo.WN_PricingPlans_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        p.IdGUID AS idGuid,
        p.Id,
        p.[Name],
        ISNULL(p.[Price], 0) AS [Price],
        p.[Description],
        f.FeatureName
    FROM dbo.WN_PricingPlans p WITH (NOLOCK)
    LEFT JOIN dbo.WN_PlanFeatures f WITH (NOLOCK) ON p.Id = f.PlanId
    WHERE p.IsActive = 1;
END
GO

-- Spaces: return GUIDs for space, location and space type
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        s.IdGUID AS idGuid,
        s.Id,
        s.[Name],
        l.IdGUID AS locationIdGuid,
        l.[Name] AS LocationName,
        st.IdGUID AS spaceTypeIdGuid,
        st.[Description] AS SpaceTypeName,
        st.Capacity,
        s.PricePerDay,
        s.pricePerHour,
        s.Amenities,
        s.ImageUrl,
        (CASE WHEN s.Status = 1 THEN 'available' ELSE 'inactive' END) AS [Status]
    FROM dbo.WN_Spaces s WITH (NOLOCK)
    LEFT JOIN dbo.WN_Locations l WITH (NOLOCK) ON s.LocationId = l.IdGUID
    LEFT JOIN dbo.WN_SpaceTypes st WITH (NOLOCK) ON s.SpaceTypeId = st.IdGUID
    WHERE s.Status != 0;
END
GO

-- Space types: ensure IdGUID returned
CREATE OR ALTER PROCEDURE dbo.WN_SpaceTypes_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        [Id],
        [IdGUID],
        [Description],
        [Capacity],
        [HourlyAllowed],
        [Status],
        [CreatedOn],
        [CreatedBy],
        [UpdatedOn],
        [UpdatedBy]
    FROM dbo.WN_SpaceTypes WITH (NOLOCK)
    WHERE [Status] = 1;
END
GO

-- Users: lookup by email must return IdGUID
CREATE OR ALTER PROCEDURE dbo.WN_Users_GetByEmail
    @Email NVARCHAR(256)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id, IdGUID FROM dbo.WN_Users WITH (NOLOCK) WHERE Email = @Email;
END
GO

-- Users: insert and return GUID
CREATE OR ALTER PROCEDURE dbo.WN_Users_Insert
    @FirstName NVARCHAR(MAX),
    @LastName NVARCHAR(MAX),
    @UserName NVARCHAR(256),
    @Email NVARCHAR(256),
    @PhoneNumber NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ExistingId INT;
    SELECT @ExistingId = Id FROM dbo.WN_Users WITH (NOLOCK) WHERE Email = @Email;

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
        SELECT @DoubleCheckId = Id FROM dbo.WN_Users WITH (NOLOCK) WHERE Email = @Email;
        IF @DoubleCheckId IS NOT NULL
        BEGIN
            ROLLBACK TRANSACTION;
            SELECT @DoubleCheckId AS NewId;
        END
        ELSE
        BEGIN
            DECLARE @NewUserGUID UNIQUEIDENTIFIER = NEWID();
            INSERT INTO dbo.WN_Users (IdGUID, Name, CreatedOn, UserName, Email, PhoneNumber)
            VALUES (@NewUserGUID, LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))), GETDATE(), @UserName, @Email, @PhoneNumber);

            SELECT @NewId = SCOPE_IDENTITY();
            COMMIT TRANSACTION;
            SELECT @NewId AS NewId, @NewUserGUID AS NewIdGuid;
        END
    END
END
GO

-- Users list: include idGuid
CREATE OR ALTER PROCEDURE dbo.WN_Users_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        u.IdGUID AS idGuid,
        u.Id AS id,
        u.Email AS email,
        u.Name AS firstName,
        u.PhoneNumber AS phone,
        u.CreatedOn AS createdAt
    FROM dbo.WN_Users u WITH (NOLOCK)
    ORDER BY u.CreatedOn DESC;
END
GO

-- Bookings: list all bookings include GUID and join fixes
CREATE OR ALTER PROCEDURE dbo.WN_Bookings_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        b.IdGUID AS idGuid,
        b.Id AS id,
        u.Email AS userEmail,
        s.Name AS spaceName,
        b.StartDateTime AS startDateTime,
        b.EndDateTime AS endDateTime,
        b.TotalAmount AS totalAmount,
        b.Notes AS notes,
        b.BookingDate AS createdAt,
        CASE
            WHEN b.BookingStatus = 2 THEN 'Cancelled'
            WHEN b.BookingStatus = 3 THEN 'Rejected'
            WHEN b.BookingStatus = 1 THEN 'Pending'
            ELSE 'Confirmed'
        END AS bookingStatus
    FROM dbo.WN_Bookings b WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users u WITH (NOLOCK) ON b.UserGuid = u.IdGUID
    LEFT JOIN dbo.WN_Spaces s WITH (NOLOCK) ON b.SpaceGuid = s.IdGUID
    WHERE b.Status = 1
    ORDER BY b.BookingDate DESC;
END
GO

-- Payments: list all payments include GUID
CREATE OR ALTER PROCEDURE dbo.WN_Payments_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        p.IdGUID AS idGuid,
        p.Id AS id,
        u.Email AS userEmail,
        p.Amount AS amount,
        p.PaymentMethod AS paymentMethod,
        p.PaymentStatus AS paymentStatus,
        p.TransactionRef AS transactionRef,
        p.PaidAt AS paidAt
    FROM dbo.WN_Payments p WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users u WITH (NOLOCK) ON p.UserId = u.IdGUID
    ORDER BY p.PaidAt DESC;
END
GO

-- Contacts/book tour list: include GUID
CREATE OR ALTER PROCEDURE dbo.WN_Contacts_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        b.IdGUID AS idGuid,
        b.Id AS id,
        b.Name AS fullName,
        b.Email AS email,
        b.PhoneNumber AS phone,
        b.Message AS message,
        b.CreatedOn AS createdAt
    FROM dbo.WN_BookTour b WITH (NOLOCK)
    WHERE b.Status = 1
    ORDER BY b.CreatedOn DESC;
END
GO

-- Memberships: include idGuid
CREATE OR ALTER PROCEDURE dbo.WN_Memberships_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        m.IdGUID AS idGuid,
        m.Id AS id,
        u.Email AS userEmail,
        p.Name AS planName,
        m.StartDate AS startDate,
        m.EndDate AS endDate,
        m.Status AS status
    FROM dbo.WN_Memberships m WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users u WITH (NOLOCK) ON m.UserId = u.IdGUID
    LEFT JOIN dbo.WN_PricingPlans p WITH (NOLOCK) ON m.PlanId = p.IdGUID
    ORDER BY m.StartDate DESC;
END
GO

-- End of migration script
PRINT 'GUID + NOLOCK migration script created. Test thoroughly before applying to production.';
GO
