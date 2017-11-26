@echo off


@echo.
@echo [ prepare workspace ]
del advinstaller\output\*   /Q /F


set /p VER= <..\version
@echo.
@echo [ updating version number : %VER% ]
C:\work\soft\AdvancedInstaller\bin\x86\AdvancedInstaller.com /edit advinstaller\bitdust.aip /SetVersion "%VER%" 


@echo.
@echo [ building .msi installer ]
C:\work\soft\AdvancedInstaller\bin\x86\AdvancedInstaller.com  /build advinstaller\bitdust.aip


@echo.
@echo [ DONE ]
@echo.

pause