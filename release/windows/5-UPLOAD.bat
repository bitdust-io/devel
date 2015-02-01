@echo off


@echo.
@echo [ prepare uploading ]
if exist upload\NUL rmdir /S /Q upload
mkdir upload
xcopy bin\* upload\    /E /R /H /Y /Q


@echo.
@echo [ upload using rsync into "test" repository ]
rsync -rptgoE --delete --force -z --compress-level=9 -h --progress -vv --stats -c  upload/* rsync://veselin@bitdust.io/test


@echo.
@echo [DONE]


pause 
