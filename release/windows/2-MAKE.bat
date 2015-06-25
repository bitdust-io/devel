@echo off

@echo.
@echo [ clear working space ]
if exist bin\NUL rmdir /S /Q bin
mkdir bin


@echo.
@echo [ copy build files ]
xcopy build\*                                   bin  /E /R /H /Y /Q


@echo.
@echo [ copy bitstarter files ]
xcopy starter\*                                 bin\ /E /R /H /Y /Q


@echo.
@echo [ fixing "unchanged" files ]
if exist unchanged\NUL xcopy unchanged\*        bin\ /E /R /H /Y /Q
if exist bin\win32com\gen_py\NUL rmdir /S /Q    bin\win32com\gen_py\


@echo.
@echo [ copy misc files ]
xcopy ..\..\LICENSE.txt                         bin\ /Y /Q
xcopy ..\..\README.txt                          bin\ /Y /Q
xcopy ..\..\CHANGELOG.txt                       bin\ /Y /Q
xcopy install.cmd                               bin\ /Y /Q
xcopy console.cmd                               bin\ /Y /Q
xcopy run.cmd                                   bin\ /Y /Q


@echo.
@echo [ copy icons ]
mkdir bin\icons
xcopy ..\..\icons\*.png                         bin\icons /Y /Q
xcopy ..\..\icons\*.ico                         bin\icons /Y /Q


@echo.
@echo [ copy fonts ]
mkdir bin\fonts
xcopy ..\..\fonts\*.ttf                         bin\fonts /Y /Q


@echo.
@echo [ patch to make pp working ]
del bin\raid\read.*
del bin\raid\make.*
del bin\raid\rebuild.*
xcopy ..\..\raid\read.py                        bin\raid\ /Y /Q
xcopy ..\..\raid\make.py                        bin\raid\ /Y /Q
xcopy ..\..\raid\rebuild.py                     bin\raid\ /Y /Q


@echo.
@echo [ create DONE ]
@echo.


pause 
