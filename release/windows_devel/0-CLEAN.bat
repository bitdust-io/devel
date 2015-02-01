@echo off


@echo.
@echo [ clear bin folder ]
if exist bin\NUL rmdir /S /Q bin


@echo.
@echo [ clear msi output folder ]
del advinstaller\output\*   /Q /F
rm -rf advinstaller\bitdust-cache\


@echo.
@echo [ clear portable files ]
if exist bitdust-development.zip del bitdust-development.zip 
if exist portable\NUL rmdir /S /Q portable
mkdir portable


@echo.
@echo [DONE]
@echo.

pause