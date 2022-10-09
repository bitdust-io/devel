@echo off

@echo.
@echo [ clear working space ]
if exist starter\NUL rmdir /S /Q starter
REM if exist ..\..\dist\NUL rmdir /S /Q ..\..\dist
if exist ..\..\build\NUL rmdir /S /Q ..\..\build
mkdir starter


@echo.
@echo [ building starter ]
cp py2exe_build_starter.py ..\..
pushd ..\..
python -OO py2exe_build_starter.py -q py2exe
rm -rf py2exe_build_starter.py
rmdir /S /Q build
popd


@echo.
@echo [ copy additional files ]
xcopy distrib3thparty\wget.exe starter\ /Y /Q
xcopy distrib3thparty\gzip.exe starter\ /Y /Q
xcopy distrib3thparty\tar.exe starter\ /Y /Q
xcopy distrib3thparty\upnpc.exe starter\ /Y /Q
xcopy Microsoft.VC90.CRT\* starter\ /Y /Q


@echo.
@echo [ DONE ]
@echo.

pause
