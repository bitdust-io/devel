@echo off


@echo.
@echo [ update revision number ]
xcopy revnum.txt                                bin\           /Y /Q
xcopy revnum.txt                                ..\..          /Y /Q
set /p REVNUM= <revnum.txt
@echo [ revision number is %REVNUM% ]


@echo.
@echo [ making checksum.txt and files.txt files ]
python checksum.py bin files.txt 1>checksum.txt 2>checksum.err


@echo.
@echo [ DONE ]
@echo.


pause 
