@echo off

@echo.
@echo [ clear working space ]
if exist bitdust.zip del bitdust.zip 
if exist portable\NUL rmdir /S /Q portable
mkdir portable


@echo.
@echo [ prepare destination folder ]
set /p VER= <..\version
mkdir portable\bitdust-%VER%
mkdir portable\bitdust-%VER%\bin
mkdir portable\bitdust-%VER%\metadata


@echo.
@echo [ copy binary files ]
xcopy bin\*   portable\bitdust-%VER%\bin  /E /R /H /Y /Q


@echo.
@echo [ create data files ]
cp appdata portable\bitdust-%VER%\bin\
cp run.~bat portable\bitdust-%VER%\run.bat
cp repo portable\bitdust-%VER%\metadata\


@echo.
@echo [ compressing files ]
cd portable\
7za.exe a -r -y ..\bitdust.zip *
cd ..\


@echo.
@echo [ DONE ]
@echo.

pause