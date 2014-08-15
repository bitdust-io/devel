@echo off


@echo.
@echo [prepare uploading space]
if exist upload\NUL rmdir /S /Q upload
mkdir upload
xcopy bin upload\    /E /R /H /Y /Q
xcopy files.txt upload\    /Y /Q
xcopy checksum.txt upload\  /Y /Q
del upload\bin\files.txt      /Q /F
del upload\bin\checksum.txt   /Q /F

@echo.
@echo [upload using rsync into "test" repository]
rsync.exe -avv upload\* rsync://veselin@bitpie.net/test

@echo.
@echo [DONE]


pause 
