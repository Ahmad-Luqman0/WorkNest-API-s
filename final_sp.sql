-- ============================================================
-- WorkNest - Final Stored Procedures Script
-- Run this entire file in SSMS against your WorkNest database
-- ============================================================
SET NOCOUNT ON;
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
        INSERT INTO dbo.WN_Users (IdGUID, Name, CreatedOn, UserName, Email, PhoneNumber)
        VALUES (@NewUserGUID,
                LTRIM(RTRIM(ISNULL(@FirstName, '') + ' ' + ISNULL(@LastName, ''))),
                GETDATE(), @UserName, @Email, @PhoneNumber);

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
    SELECT u.IdGUID    AS idGuid,
           u.Id        AS id,
           u.Email     AS email,
           u.Name      AS name,
           u.PhoneNumber AS phone,
           u.CreatedOn AS createdAt,
           u.RoleId    AS roles_int
    FROM dbo.WN_Users u WITH (NOLOCK)
    ORDER BY u.CreatedOn DESC;
END
GO

-- ── 5. WN_Locations_GetList ───────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Locations_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id        AS id,
           IdGUID    AS idGuid,
           Name      AS name,
           Address   AS address,
           City      AS city,
           OpeningTime AS openingTime,
           ClosingTime AS closingTime,
           Status    AS status
    FROM dbo.WN_Locations WITH (NOLOCK)
    WHERE Status = 1;
END
GO

-- ── 6. WN_SpaceTypes_GetList ──────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_SpaceTypes_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT Id           AS id,
           IdGUID       AS idGuid,
           Description  AS name,
           Capacity     AS capacity,
           HourlyAllowed AS hourlyAllowed,
           Status       AS status
    FROM dbo.WN_SpaceTypes WITH (NOLOCK)
    WHERE Status = 1;
END
GO

-- ── 7. WN_Spaces_GetList ──────────────────────────────────
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT s.IdGUID          AS idGuid,
           s.Id              AS id,
           s.Name            AS name,
           s.Code            AS code,
           s.Floor           AS floor,
           s.Description     AS description,
           s.PricePerDay     AS pricePerDay,
           s.PricePerHour    AS pricePerHour,
           s.Amenities       AS amenities,
           s.ImageUrl        AS imageUrl,
           s.Status          AS status,
           l.IdGUID          AS locationIdGuid,
           l.Name            AS locationName,
           st.IdGUID         AS spaceTypeIdGuid,
           st.Description    AS spaceTypeName,
           st.Capacity       AS capacity
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
    SELECT g.IdGUID   AS idGuid,
           g.Id       AS id,
           g.Title    AS title,
           g.ImageUrl AS imageUrl,
           g.SortOrder AS sortOrder,
           g.IsActive AS isActive
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
    SELECT p.IdGUID        AS idGuid,
           p.Id            AS id,
           p.Name          AS name,
           ISNULL(p.Price, 0) AS price,
           p.BillingCycle  AS billingCycle,
           p.IncludesHours AS includesHours,
           p.IsActive      AS isActive,
           p.Description   AS description,
           f.FeatureName   AS featureName
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

    SELECT b.IdGUID         AS idGuid,
           b.Id             AS id,
           s.Name           AS spaceName,
           b.StartDateTime  AS startDateTime,
           b.EndDateTime    AS endDateTime,
           b.TotalAmount    AS totalAmount,
           b.Notes          AS notes,
           b.BookingDate    AS createdAt,
           CASE b.BookingStatus
               WHEN 1 THEN 'Pending'
               WHEN 2 THEN 'Cancelled'
               WHEN 3 THEN 'Rejected'
               WHEN 4 THEN 'Confirmed'
               ELSE 'Confirmed'
           END AS bookingStatus
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
    SELECT b.IdGUID         AS idGuid,
           b.Id             AS id,
           u.Email          AS userEmail,
           s.Name           AS spaceName,
           b.StartDateTime  AS startDateTime,
           b.EndDateTime    AS endDateTime,
           b.TotalAmount    AS totalAmount,
           b.Notes          AS notes,
           b.BookingDate    AS createdAt,
           CASE b.BookingStatus
               WHEN 1 THEN 'Pending'
               WHEN 2 THEN 'Cancelled'
               WHEN 3 THEN 'Rejected'
               WHEN 4 THEN 'Confirmed'
               ELSE 'Confirmed'
           END AS bookingStatus
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

    SELECT p.IdGUID          AS idGuid,
           p.Id              AS id,
           p.Amount          AS amount,
           p.PaymentMethod   AS paymentMethod,
           p.PaymentStatus   AS paymentStatus,
           p.PaidAt          AS paidAt,
           p.TransactionRef  AS referenceNumber,
           s.Name            AS workspaceName,
           b.StartDateTime   AS start_date,
           b.EndDateTime     AS end_date
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
    SELECT p.IdGUID         AS idGuid,
           p.Id             AS id,
           u.Email          AS userEmail,
           p.Amount         AS amount,
           p.PaymentMethod  AS paymentMethod,
           p.PaymentStatus  AS paymentStatus,
           p.TransactionRef AS transactionRef,
           p.PaidAt         AS paidAt
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
    SELECT b.IdGUID     AS idGuid,
           b.Id         AS id,
           b.Name       AS fullName,
           b.Email      AS email,
           b.PhoneNumber AS phone,
           b.Message    AS message,
           b.CreatedOn  AS createdAt,
           b.Status     AS status
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
    SELECT m.IdGUID    AS idGuid,
           m.Id        AS numericId,
           u.Email     AS userEmail,
           pp.Name     AS planName,
           pp.Price    AS planPrice,
           pp.BillingCycle AS planCycle,
           m.StartDate AS startDate,
           m.EndDate   AS endDate,
           m.Status    AS status
    FROM dbo.WN_Memberships m WITH (NOLOCK)
    LEFT JOIN dbo.WN_Users        u  WITH (NOLOCK) ON m.UserGuid = u.IdGUID
    LEFT JOIN dbo.WN_PricingPlans pp WITH (NOLOCK) ON m.PlanId   = pp.Id
    WHERE m.Status != 0
    ORDER BY m.StartDate DESC;
END
GO

PRINT 'All WorkNest stored procedures created successfully.';
GO
