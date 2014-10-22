@echo off

@echo.
@echo [ need to stop BitPie.NET first ]
tasklist /FI "IMAGENAME eq bitpie.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bitpie.exe" >NUL && ( taskkill  /IM bitpie.exe /F /T )
tasklist /FI "IMAGENAME eq bpstarter.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bpstarter.exe" >NUL && ( taskkill  /IM bpstarter.exe /F /T )
tasklist /FI "IMAGENAME eq bpgui.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bpgui.exe" >NUL && ( taskkill  /IM bpgui.exe /F /T )
tasklist /FI "IMAGENAME eq bppipe.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bppipe.exe" >NUL && ( taskkill  /IM bppipe.exe /F /T )
tasklist /FI "IMAGENAME eq bptester.exe" 2>NUL | c:\windows\system32\find.exe /I /N "bptester.exe" >NUL && ( taskkill  /IM bptester.exe /F /T )

sleep 2

@echo.
@echo [ replacing files ]
pushd "%USERPROFILE%\.bitpie"
if exist bin.off\NUL rmdir /S /Q bin.off
if exist bin\NUL rename bin bin.off
mkdir bin
popd
xcopy "bin\*" "%USERPROFILE%\.bitpie\bin\" /E /R /H /Y /Q
cd "%USERPROFILE%\.bitpie\bin\"


@echo.
@echo [ GO ! ]
@echo.

bitpie.exe show


@echo.
@echo [ replacing files back ]
cd ..
rmdir /S /Q bin
if exist bin.off\NUL mv bin.off bin

@echo.
@echo [ FINISHED ]
@echo.

pause


