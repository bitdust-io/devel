@echo off

@echo.
@echo [ need to stop BitDust first ]
tasklist /FI "IMAGENAME eq bitdust.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bitdust.exe" >NUL && ( taskkill  /IM bitdust.exe /F /T )
tasklist /FI "IMAGENAME eq bpstarter.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bpstarter.exe" >NUL && ( taskkill  /IM bpstarter.exe /F /T )
tasklist /FI "IMAGENAME eq bpgui.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bpgui.exe" >NUL && ( taskkill  /IM bpgui.exe /F /T )
tasklist /FI "IMAGENAME eq bppipe.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bppipe.exe" >NUL && ( taskkill  /IM bppipe.exe /F /T )
tasklist /FI "IMAGENAME eq bptester.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bptester.exe" >NUL && ( taskkill  /IM bptester.exe /F /T )

sleep 2

@echo.
@echo [ replacing files ]
pushd "%USERPROFILE%\.bitdust"
rm -rf bin.off
mkdir bin.off
xcopy "bin\*.*" "bin.off\" /E /R /H /Y /Q
rm -rf bin
mkdir bin
popd
xcopy "bin\*.*" "%USERPROFILE%\.bitdust\bin\" /E /R /H /Y /Q
cd "%USERPROFILE%\.bitdust\bin\"


@echo.
@echo [ GO ! ]
@echo.

rem START cmd /k "cd %USERPROFILE%\.bitdust\bin\ & echo Welcome to BitDust project! & echo Type `bitdust usage` to list all available commands and options."

bitdust.exe show


@echo.
@echo [ press a key when the program is finished ]
pause

rem @echo.
rem @echo [ replacing files back ]
rem cd ..
rem rmdir /S /Q bin
rem if exist bin.off\NUL mv bin.off bin

rem @echo.
rem @echo [ FINISHED ]
rem @echo.

rem pause
