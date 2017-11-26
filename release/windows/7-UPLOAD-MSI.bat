@echo off

@echo.
@echo [ upload bitdust-testing.msi to bitdust.io ]
pushd advinstaller\output\
rename bitdust.msi bitdust-testing.msi
REM scp bitdust-testing.msi veselin@bitdust.io:/var/www/download
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-testing.msi rsync://veselin@bitdust.io/download
popd
REM ssh veselin@bitdust.io "chmod u+x /var/www/download/bitdust-testing.msi"

@echo.
@echo [ DONE ]
@echo.

pause
