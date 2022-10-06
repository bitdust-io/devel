@echo off

@echo.
@echo [ clear working space ]
if exist bin\NUL rmdir /S /Q bin
mkdir bin


@echo.
@echo [ copy files from local testing repo ]
xcopy ..\windows\upload\*      bin\      /E /R /H /Y /Q


@echo.
@echo [ create DONE ]
@echo.

pause
