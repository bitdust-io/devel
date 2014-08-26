@echo off


@echo.
@echo [ clear working space ]
if exist ..\..\build\NUL rmdir /S /Q ..\..\build
if exist build\NUL rmdir /S /Q build
mkdir build


@echo.
@echo [ doing "git pull" in root ]
pushd ..\..
git pull 
popd


@echo.
@echo [ building release ]
cp py2exe_build.py ..\..
pushd ..\..
python -OO py2exe_build.py -q py2exe
rm -rf py2exe_build.py
rmdir /S /Q build
popd


@echo.
@echo [ build DONE ]
@echo.

pause 


