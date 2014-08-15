@echo off

@echo.
@echo [ clear working space ]
if exist starter\NUL rmdir /S /Q starter
if exist ..\..\dist\NUL rmdir /S /Q ..\..\dist
if exist ..\..\build\NUL rmdir /S /Q ..\..\build
mkdir starter


@echo.
@echo [ building starter ]
cp py2exe_build_starter.py ..\..
pushd ..\..
python -OO py2exe_build_starter.py -q py2exe
rm -rf py2exe_build_starter.py
popd


@echo.
@echo [ copy files ]
xcopy ..\..\dist\* starter\ /E /R /H /Y /Q
xcopy distrib3thparty\wget.exe starter\ /Y /Q
xcopy distrib3thparty\gzip.exe starter\ /Y /Q
xcopy distrib3thparty\tar.exe starter\ /Y /Q
xcopy distrib3thparty\upnpc.exe starter\ /Y /Q
xcopy Microsoft.VC90.CRT\* starter\ /Y /Q


rmdir /S /Q ..\..\dist
rmdir /S /Q ..\..\build


@echo.
@echo [ DONE ]
@echo.

pause 

