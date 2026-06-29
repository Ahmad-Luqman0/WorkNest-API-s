-- ============================================================
-- Add SecurityDeposit column to WN_SpaceConfig
-- Run ONCE against the WorkNest database in SSMS
-- ============================================================

USE [SAC400]
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_SpaceConfig')
      AND name = 'SecurityDeposit'
)
BEGIN
    ALTER TABLE dbo.WN_SpaceConfig
    ADD SecurityDeposit DECIMAL(10,2) NOT NULL DEFAULT 0;
    PRINT 'SecurityDeposit column added to WN_SpaceConfig.';
END
GO

-- Update the GetConfig SP to include SecurityDeposit
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_GetConfig
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        Id, SpaceCategory, TotalSpaces, CodePrefix, MinCode,
        DefaultCapacities, OpeningTime, ClosingTime,
        SecurityDeposit, UpdatedOn, UpdatedBy
    FROM dbo.WN_SpaceConfig
    ORDER BY Id;
END
GO

-- Update the UpdateConfig SP to support SecurityDeposit
CREATE OR ALTER PROCEDURE dbo.WN_Spaces_UpdateConfig
    @SpaceCategory      NVARCHAR(20),
    @TotalSpaces        INT,
    @DefaultCapacities  NVARCHAR(50)  = NULL,
    @OpeningTime        NVARCHAR(5)   = NULL,
    @ClosingTime        NVARCHAR(5)   = NULL,
    @AdminEmail         NVARCHAR(255) = NULL,
    @SecurityDeposit    DECIMAL(10,2) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.WN_SpaceConfig
    SET TotalSpaces       = @TotalSpaces,
        DefaultCapacities = ISNULL(@DefaultCapacities, DefaultCapacities),
        OpeningTime       = ISNULL(@OpeningTime,       OpeningTime),
        ClosingTime       = ISNULL(@ClosingTime,       ClosingTime),
        SecurityDeposit   = ISNULL(@SecurityDeposit,   SecurityDeposit),
        UpdatedOn         = GETUTCDATE(),
        UpdatedBy         = @AdminEmail
    WHERE SpaceCategory = @SpaceCategory;

    SELECT @@ROWCOUNT AS AffectedRows;
END
GO

PRINT 'Security deposit migration completed.';
GO
