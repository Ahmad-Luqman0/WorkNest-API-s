-- Step 1: Ensure WN_Amenities table exists and is seeded
IF NOT EXISTS (SELECT 1 FROM sysobjects WHERE name='WN_Amenities' AND xtype='U')
CREATE TABLE dbo.WN_Amenities (
    Id     INT IDENTITY(1,1) PRIMARY KEY,
    Name   NVARCHAR(100) NOT NULL,
    Status TINYINT NOT NULL DEFAULT 1
);

-- Seed default amenities (skip if already seeded)
IF NOT EXISTS (SELECT 1 FROM dbo.WN_Amenities)
INSERT INTO dbo.WN_Amenities (Name) VALUES
('WiFi'), ('Projector'), ('Whiteboard'), ('Air Conditioning'),
('Standing Desk'), ('Coffee Machine'), ('Printer'), ('Locker');

-- Step 2: Ensure WN_Floors table exists
IF NOT EXISTS (SELECT 1 FROM sysobjects WHERE name='WN_Floors' AND xtype='U')
CREATE TABLE dbo.WN_Floors (
    Id         INT IDENTITY(1,1) PRIMARY KEY,
    LocationId INT NOT NULL,
    FloorName  NVARCHAR(100) NOT NULL,
    Status     TINYINT NOT NULL DEFAULT 1,
    CreatedOn  DATETIME DEFAULT GETDATE()
);

-- Step 2b: Add FloorId column to WN_Spaces if not exists
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.WN_Spaces') AND name = 'FloorId')
    ALTER TABLE dbo.WN_Spaces ADD FloorId INT NULL;

-- Step 2c: Migrate existing Floor string values into WN_Floors and set FloorId
DECLARE @SId INT, @SLocationNumericId INT, @FloorStr NVARCHAR(100), @FloorId INT;

DECLARE floor_cur CURSOR FOR
    SELECT s.Id,
           l.Id AS LocationNumericId,
           s.Floor
    FROM dbo.WN_Spaces s
    LEFT JOIN dbo.WN_Locations l ON s.LocationId = l.IdGUID
    WHERE s.Floor IS NOT NULL AND LEN(LTRIM(RTRIM(s.Floor))) > 0
      AND s.FloorId IS NULL;

OPEN floor_cur;
FETCH NEXT FROM floor_cur INTO @SId, @SLocationNumericId, @FloorStr;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @FloorId = NULL;
    SET @FloorStr = LTRIM(RTRIM(@FloorStr));

    SELECT @FloorId = Id FROM dbo.WN_Floors
    WHERE LocationId = @SLocationNumericId
      AND LOWER(FloorName) = LOWER(@FloorStr)
      AND Status = 1;

    IF @FloorId IS NULL
    BEGIN
        INSERT INTO dbo.WN_Floors (LocationId, FloorName, Status)
        VALUES (@SLocationNumericId, @FloorStr, 1);
        SET @FloorId = SCOPE_IDENTITY();
    END

    UPDATE dbo.WN_Spaces SET FloorId = @FloorId WHERE Id = @SId;

    FETCH NEXT FROM floor_cur INTO @SId, @SLocationNumericId, @FloorStr;
END

CLOSE floor_cur;
DEALLOCATE floor_cur;

-- Step 2d: Drop the old Floor string column now that FloorId is populated
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.WN_Spaces') AND name = 'Floor')
    ALTER TABLE dbo.WN_Spaces DROP COLUMN Floor;

-- Step 3: Convert existing comma-separated amenity NAMES to comma-separated IDs
-- This cursor processes each space that has a non-numeric amenities string
DECLARE @SpaceId INT, @AmenitiesStr NVARCHAR(MAX), @NewIds NVARCHAR(MAX);
DECLARE @Token NVARCHAR(200), @AmenityId INT;

DECLARE space_cur CURSOR FOR
    SELECT Id, Amenities FROM dbo.WN_Spaces
    WHERE Amenities IS NOT NULL AND LEN(LTRIM(RTRIM(Amenities))) > 0
      AND Amenities LIKE '%[^0-9,]%';  -- has at least one non-digit/non-comma char (still name-based)

OPEN space_cur;
FETCH NEXT FROM space_cur INTO @SpaceId, @AmenitiesStr;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @NewIds = '';

    -- Split by comma using XML trick
    DECLARE @xml XML = CAST('<i>' + REPLACE(@AmenitiesStr, ',', '</i><i>') + '</i>' AS XML);

    DECLARE token_cur CURSOR FOR
        SELECT LTRIM(RTRIM(n.value('.', 'NVARCHAR(200)'))) FROM @xml.nodes('i') AS x(n);

    OPEN token_cur;
    FETCH NEXT FROM token_cur INTO @Token;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        -- If token is already a number, use it directly; else look up by name
        IF ISNUMERIC(@Token) = 1
            SET @AmenityId = CAST(@Token AS INT);
        ELSE
        BEGIN
            SELECT @AmenityId = Id FROM dbo.WN_Amenities
            WHERE LOWER(LTRIM(RTRIM(Name))) = LOWER(@Token) AND Status = 1;

            -- If not found, insert it
            IF @AmenityId IS NULL
            BEGIN
                INSERT INTO dbo.WN_Amenities (Name) VALUES (@Token);
                SET @AmenityId = SCOPE_IDENTITY();
            END
        END

        IF @AmenityId IS NOT NULL
            SET @NewIds = @NewIds + CASE WHEN @NewIds = '' THEN '' ELSE ',' END + CAST(@AmenityId AS NVARCHAR(10));

        SET @AmenityId = NULL;
        FETCH NEXT FROM token_cur INTO @Token;
    END

    CLOSE token_cur;
    DEALLOCATE token_cur;

    IF LEN(@NewIds) > 0
        UPDATE dbo.WN_Spaces SET Amenities = @NewIds WHERE Id = @SpaceId;

    FETCH NEXT FROM space_cur INTO @SpaceId, @AmenitiesStr;
END

CLOSE space_cur;
DEALLOCATE space_cur;
