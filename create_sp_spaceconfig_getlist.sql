USE [SAC400]
GO

CREATE OR ALTER PROCEDURE dbo.WN_SpaceConfig_GetList
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        Id, SpaceCategory, TotalSpaces, CodePrefix, MinCode,
        DefaultCapacities, OpeningTime, ClosingTime,
        ISNULL(SecurityDeposit, 0) AS SecurityDeposit,
        UpdatedOn, UpdatedBy
    FROM dbo.WN_SpaceConfig
    ORDER BY Id;
END
GO

-- Verify
EXEC dbo.WN_SpaceConfig_GetList;
GO
