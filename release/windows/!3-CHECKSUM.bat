@echo off


@echo.
@echo [ update revision number ]
git rev-list --count HEAD >revnum
xcopy revnum                                bin\           /Y /Q
set /p REVNUM= <revnum


@echo.
@echo current version number is: 
type version
python -c "v=list(open('version').read().split('.'));v[-2]=str(int(v[-2])+1);v[-1]=open('revnum').read();open('version','w').write('.'.join(v))"
xcopy version   bin\     /Y /Q
@echo.
@echo new version is: 
type version
@echo.


@echo.
@echo [ revision number is %REVNUM% ]


@echo.
@echo [ generate md5 hashes in "checksum" and "files" ]
python checksum.py bin files 1>checksum
@echo.


@echo.
@echo [ DONE ]
@echo.


pause 
