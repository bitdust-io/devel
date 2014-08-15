@echo off


@echo.
@echo [ clear working space ]
if exist ..\..\dist\NUL rmdir /S /Q ..\..\dist
if exist ..\..\build\NUL rmdir /S /Q ..\..\build
if exist bin\NUL rmdir /S /Q bin
mkdir bin
if exist build\NUL rmdir /S /Q build
mkdir build


@echo.
@echo [ doing "git pull" in root ]
pushd ..\..
git pull 
popd


@echo.
@echo [ update revision number for HEAD branch ]
git rev-list --count HEAD >revnum.txt


@echo.
@echo current version number is: 
type version_number
python -c "v=list(open('version_number').read().split('.'));v[-2]=str(int(v[-2])+1);v[-1]=open('revnum.txt').read();open('version_number','w').write('.'.join(v))"
@echo.
@echo new version is: 
type version_number
@echo.


@echo.
@echo [ building release ]
cp py2exe_build.py ..\..
pushd ..\..
python -OO py2exe_build.py -q py2exe
rm -rf py2exe_build.py
popd

@echo.
@echo It is fine?
pause

@echo.
@echo [ copy binary files ]
xcopy ..\..\dist\*.*     build\    /E /R /H /Y /Q
rmdir /S /Q ..\..\dist
rmdir /S /Q ..\..\build


@echo.
@echo [ build DONE ]
@echo.

pause 


