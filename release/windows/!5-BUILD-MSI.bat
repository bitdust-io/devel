@echo off


@echo.
@echo [ copy binaries files to the source dir ]
rmdir advinstaller\src\bin      /S /Q
mkdir advinstaller\src\bin
xcopy  bin\*  advinstaller\src\bin   /E /R /H /Y /Q


set /p VER= <version_number
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