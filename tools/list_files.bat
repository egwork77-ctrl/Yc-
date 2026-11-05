@echo off
REM AOI machine file listing (READ-ONLY). Works on old Windows (XP / 2000).
REM Usage: copy to a USB drive, double-click on the machine PC.
REM Output: aoi_files_<COMPUTERNAME>.txt on the USB drive. Nothing is modified or deleted.
set OUT=%~dp0aoi_files_%COMPUTERNAME%.txt
echo Computer: %COMPUTERNAME% > "%OUT%"
echo Date: %DATE% %TIME% >> "%OUT%"
for %%D in (C D E F) do if exist %%D:\ (
  echo ===== %%D: ===== >> "%OUT%"
  dir %%D:\*.log %%D:\*.txt %%D:\*.csv %%D:\*.xml %%D:\*.ini %%D:\*.cal %%D:\*.dat /s /o-d /t:w >> "%OUT%" 2^>nul
)
echo Done. Result: %OUT%
pause
