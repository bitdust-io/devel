@echo off


@echo.
@echo [ clear working space ]
if exist build\NUL rmdir /S /Q build
mkdir build
mkdir build\src
mkdir build\python
mkdir build\git
mkdir build\bin
mkdir build\icons


@echo.
@echo [ copy python files from bitdust.environment ]
xcopy ..\..\..\bitdust.environment\python279_win32\* build\python /E /R /H /Y /Q


@echo.
@echo [ copy git files from bitdust.environment ]
xcopy ..\..\..\bitdust.environment\git\* build\git /E /R /H /Y /Q


@echo.
@echo [ create .bat aliases ]
xcopy aliases\* build\bin /E /R /H /Y /Q 


@echo.
@echo [ copy icons ]
xcopy ..\..\icons\* build\icons /E /R /H /Y /Q 


@echo.
@echo [ build DONE ]
@echo.

pause