@echo off

@echo.
@echo [ clear working space ]
if exist bitpie.zip del bitpie.zip 
if exist portable\NUL rmdir /S /Q portable
mkdir portable


@echo.
@echo [ prepare destination folder ]
set /p VER= <..\version
mkdir portable\bitpie-%VER%
mkdir portable\bitpie-%VER%\bin
mkdir portable\bitpie-%VER%\metadata


@echo.
@echo [ copy binary files ]
xcopy bin\*   portable\bitpie-%VER%\bin  /E /R /H /Y /Q


@echo.
@echo [ create data files ]
cp appdata portable\bitpie-%VER%\bin\
cp run.~bat portable\bitpie-%VER%\run.bat
cp repo portable\bitpie-%VER%\metadata\


@echo.
@echo [ compressing files ]
cd portable\
7za.exe a -r -y ..\bitpie.zip *
cd ..\


@echo.
@echo [ DONE ]
@echo.

pause