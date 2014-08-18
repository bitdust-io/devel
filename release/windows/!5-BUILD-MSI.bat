@echo off


@echo.
@echo [ prepare workspace ]
if exist advinstaller\src\bin\NUL rmdir advinstaller\src\bin      /S /Q
mkdir advinstaller\src\bin
xcopy  bin\*  advinstaller\src\bin   /E /R /H /Y /Q
del advinstaller\output\*   /Q /F


set /p VER= <version
@echo.
@echo [ updating version number : %VER% ]
C:\work\soft\AdvancedInstaller\bin\x86\AdvancedInstaller.com /edit advinstaller\bitpie.aip /SetVersion "%VER%" 

@echo.
@echo [ building .msi installer ]
C:\work\soft\AdvancedInstaller\bin\x86\AdvancedInstaller.com /build advinstaller\bitpie.aip 


@echo.
@echo [ DONE ]
@echo.

pause