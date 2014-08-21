@echo off


@echo.
@echo [ update revision number ]
git rev-list --count HEAD >revnum
set /p REVNUM= <revnum

@echo.
@echo revision number is %REVNUM% 


@echo.
@echo current version number is: 
type ..\version
python -c "v=list(open('..\version').read().split('.'));v[-2]=str(int(v[-2])+1);v[-1]=open('revnum').read().strip();open('..\version','w').write('.'.join(v))"
xcopy ..\version   bin\     /Y /Q
del revnum
@echo.
@echo new version is: 
type ..\version
set /p VER= <..\version
@echo.



@echo.
@echo [ version UPDATED ]
@echo.
