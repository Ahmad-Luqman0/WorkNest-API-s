-- Run this FIRST in SSMS to drop all old SPs, then run space_config_migration.sql
USE [WorkNest]
GO
IF OBJECT_ID('dbo.WN_Booking_Create',            'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_Create;
GO
IF OBJECT_ID('dbo.WN_Booking_AssignClosestSpace', 'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_AssignClosestSpace;
GO
IF OBJECT_ID('dbo.WN_Booking_GetAvailableSpaces', 'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_GetAvailableSpaces;
GO
IF OBJECT_ID('dbo.WN_Booking_CheckOverlap',       'P') IS NOT NULL DROP PROCEDURE dbo.WN_Booking_CheckOverlap;
GO
IF OBJECT_ID('dbo.WN_Spaces_GenerateInventory',   'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_GenerateInventory;
GO
IF OBJECT_ID('dbo.WN_Spaces_UpdateConfig',        'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_UpdateConfig;
GO
IF OBJECT_ID('dbo.WN_Spaces_GetConfig',           'P') IS NOT NULL DROP PROCEDURE dbo.WN_Spaces_GetConfig;
GO
PRINT 'All target SPs dropped. Now run space_config_migration.sql';
GO
