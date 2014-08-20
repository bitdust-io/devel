@echo off

@echo.
@echo [ clear working space ]
if exist bin\NUL rmdir /S /Q bin
mkdir bin


@echo.
@echo [ copy files from local development repo ]
xcopy ..\windows_devel\bin\*      bin\      /E /R /H /Y /Q 


@echo.
@echo [ create DONE ]
@echo.

pause 


