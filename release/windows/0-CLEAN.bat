@echo off


@echo.
@echo [ clear build folder ]
if exist ..\..\build\NUL rmdir /S /Q ..\..\build
if exist build\NUL rmdir /S /Q build
mkdir build


@echo.
@echo [ clear bin folder ]
if exist bin\NUL rmdir /S /Q bin


@echo.
@echo [ clear msi output folder ]
del advinstaller\output\*   /Q /F
rm -rf advinstaller/bitdust-cache/


@echo.
@echo [ clear uploading folder ]
if exist upload\NUL rmdir /S /Q upload
mkdir upload


@echo.
@echo [ clear portable folder ]
if exist bitdust-testing.zip del bitdust-testing.zip
if exist portable\NUL rmdir /S /Q portable
mkdir portable


@echo.
@echo [DONE]
@echo.

pause
