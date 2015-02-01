@echo off


@echo.
@echo [ check if BitDust is running at the moment and stop all processes found ]
tasklist /FI "IMAGENAME eq bitdust.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bitdust.exe" >NUL && ( taskkill  /IM bitdust.exe /F /T )
tasklist /FI "IMAGENAME eq bitstarter.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bitstarter.exe" >NUL && ( taskkill  /IM bitstarter.exe /F /T )
tasklist /FI "IMAGENAME eq bpgui.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bpgui.exe" >NUL && ( taskkill  /IM bpgui.exe /F /T )
tasklist /FI "IMAGENAME eq bppipe.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bppipe.exe" >NUL && ( taskkill  /IM bppipe.exe /F /T )
tasklist /FI "IMAGENAME eq bptester.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bptester.exe" >NUL && ( taskkill  /IM bptester.exe /F /T )

sleep 2

@echo.
@echo [ replacing files ]
rmdir "%USERPROFILE%\.bitdust\bin" /S /Q 
mkdir "%USERPROFILE%\.bitdust\bin"
xcopy "bin\*" "%USERPROFILE%\.bitdust\bin\" /E /R /H /Y /Q
cd "%USERPROFILE%\.bitdust\bin\"


@echo.
@echo [ GO ! ]
@echo.

bitdust.exe show


@echo.
@echo [ FINISHED ]
@echo.

pause
