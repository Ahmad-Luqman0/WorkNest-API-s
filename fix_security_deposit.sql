USE [SAC400]
GO

-- Step 1: Add column if missing
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_SpaceConfig') AND name = 'SecurityDeposit'
)
BEGIN
    ALTER TABLE dbo.WN_SpaceConfig
    ADD SecurityDeposit DECIMAL(10,2) NOT NULL DEFAULT 0;
    PRINT 'Column added.';
END
GO

-- Step 2: Set the value
UPDATE dbo.WN_SpaceConfig SET SecurityDeposit = 90000 WHERE SpaceCategory = 'Private';
GO

-- Step 3: Recreate SP to include SecurityDeposit
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

-- Step 4: Verify
SELECT SpaceCategory, SecurityDeposit FROM dbo.WN_SpaceConfig;
EXEC dbo.WN_Spaces_GetConfig;
GO
