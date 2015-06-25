@echo off


@echo.
@echo [ clear working space ]
if exist build\NUL rmdir /S /Q build
mkdir build
mkdir build\src


REM @echo.
REM @echo [ doing "git pull" in root ]
REM SET curpath=%cd%\build
REM pushd ..\..
REM git pull 


@echo.
@echo [ run "python dbuilder.py" ]
python dbuilder.py -j --dist-dir=./build/src ..\sources\workspace\bitdust\


@echo.
@echo [ build DONE ]
@echo.

pause 


