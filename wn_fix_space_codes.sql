-- ============================================================
-- WorkNest: Fix existing space codes + update SpaceConfig
-- Run this in SSMS against SAC400
-- ============================================================
USE [SAC400]
GO

-- ============================================================
-- Step 1: Add SpaceTypeId column to WN_SpaceConfig if missing
-- ============================================================
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.WN_SpaceConfig') AND name = 'SpaceTypeId'
)
    ALTER TABLE dbo.WN_SpaceConfig ADD SpaceTypeId INT NULL;
GO

-- Step 2: Set SpaceTypeId values in WN_SpaceConfig
-- Co-Working Space (Id=2) → Shared
-- Private Office  (Id=1) → Private
-- Meeting Room    (Id=3) → Meeting
UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 2 WHERE SpaceCategory = 'Shared';
UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 1 WHERE SpaceCategory = 'Private';
UPDATE dbo.WN_SpaceConfig SET SpaceTypeId = 3 WHERE SpaceCategory = 'Meeting';
GO
PRINT 'Step 2 done: SpaceTypeId set in WN_SpaceConfig';
GO

-- Step 3: Update existing active spaces to use new numeric codes
-- Space Id=1 'Private Office'  (SpaceTypeId=1 Private)  → code 3101
-- Space Id=2 'Shared Space'    (SpaceTypeId=2 Shared)   → code 3001
-- Space Id=3 'Meeting Room'    (SpaceTypeId=3 Meeting)  → code 3201
-- Space Id=8 'Private 1'       (SpaceTypeId=1 Private)  → code 3102

DECLARE @PvtGuid UNIQUEIDENTIFIER;
DECLARE @SwdGuid UNIQUEIDENTIFIER;
DECLARE @MtgGuid UNIQUEIDENTIFIER;

SELECT @PvtGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 1;
SELECT @SwdGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 2;
SELECT @MtgGuid = IdGUID FROM dbo.WN_SpaceTypes WHERE Id = 3;

-- Update Space 1: Private Office → code 3101, link to Private Office type
UPDATE dbo.WN_Spaces SET Code = '3101', SpaceTypeId = @PvtGuid WHERE Id = 1;
-- Update Space 2: Shared Space → code 3001, link to Co-Working Space type
UPDATE dbo.WN_Spaces SET Code = '3001', SpaceTypeId = @SwdGuid WHERE Id = 2;
-- Update Space 3: Meeting Room → code 3201, link to Meeting Room type
UPDATE dbo.WN_Spaces SET Code = '3201', SpaceTypeId = @MtgGuid WHERE Id = 3;
-- Update Space 8: Private 1 → code 3102
UPDATE dbo.WN_Spaces SET Code = '3102', SpaceTypeId = @PvtGuid WHERE Id = 8;
GO
PRINT 'Step 3 done: Space codes updated to numeric convention';
GO

PRINT 'Data fix completed. Spaces now use codes: 3001(Shared), 3101-3102(Private), 3201(Meeting)';
GO
