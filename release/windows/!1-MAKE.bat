@echo off


@echo.
@echo [ copy build files ]
xcopy build\*                                   bin  /E /R /H /Y /Q


@echo.
@echo [ copy starter files ]
xcopy starter\*                                 bin\ /E /R /H /Y /Q


REM @echo.
REM @echo [ fixing "unchanged" files ]
REM if exist unchanged\NUL xcopy unchanged\*        bin\ /E /R /H /Y /Q
REM if exist bin\win32com\gen_py\NUL rmdir /S /Q    bin\win32com\gen_py\


@echo.
@echo [ copy misc files ]
xcopy ..\..\LICENSE.txt                         bin\ /Y /Q
xcopy ..\..\README.txt                          bin\ /Y /Q


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
@echo [ create DONE ]
@echo.


pause 
