@echo off


set /p VER= <..\version
xcopy ..\version   bin\     /Y /Q

@echo. 
@echo [ update version number ( %VER% ) in binaries ]
set FILEDESCR=/s desc "BitPie.NET - Easy as a pie"
set BUILDINFO=/s pb "Built by Veselin Penev"
set COMPINFO=/s company "BitPie.NET Inc." /s (c) "(c) BitPie.NET Inc. 2014."
set PRODINFO=/s product "BitPie.NET" /pv "%VER%"
verpatch /va bin\bitpie.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%
verpatch /va bin\bpstarter.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%
verpatch /va bin\bppipe.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%
verpatch /va bin\bpgui.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%
verpatch /va bin\bptester.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%
verpatch /va bin\bpworker.exe %VER% %FILEDESCR% %COMPINFO% %PRODINFO% %BUILDINFO%


@echo.
@echo [ generate md5 hashes in "checksum" and "files" ]
python checksum.py bin files 1>checksum
xcopy checksum bin\ /Y /Q
xcopy files bin\  /Y /Q
@echo.


@echo.
@echo [ DONE ]
@echo.


pause 
