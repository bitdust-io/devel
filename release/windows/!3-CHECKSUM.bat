@echo off


@echo.
@echo [ update revision number ]
git rev-list --count HEAD >revnum
REM xcopy revnum                                bin\           /Y /Q
set /p REVNUM= <revnum


@echo.
@echo current version number is: 
type version
python -c "v=list(open('version').read().split('.'));v[-2]=str(int(v[-2])+1);v[-1]=open('revnum').read();open('version','w').write('.'.join(v))"
xcopy version   bin\     /Y /Q
@echo.
@echo new version is: 
type version
set /p VER= <version
@echo.


@echo.
@echo [ revision number is %REVNUM% ]


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
