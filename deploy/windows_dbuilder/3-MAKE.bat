@echo off


@echo.
@echo [ erase some files ]
cd build\src
rm -f MANIFEST.in
cd ..\..


@echo.
@echo [ copy files from bitdust.environment ]
mkdir build\python
xcopy ..\..\..\bitdust.environment\python279\* build\python /E /R /H /Y /Q


@echo.
@echo [ create aliases ]
mkdir build\bin
xcopy aliases\* build\bin /E /R /H /Y /Q 


@echo.
@echo [ make DONE ]
@echo.

pause 