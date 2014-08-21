@echo off

@echo.
@echo [ upload bitpie-testing.msi to bitpie.net ]
pushd advinstaller\output\
rename bitpie.msi bitpie-testing.msi
REM scp bitpie-testing.msi veselin@bitpie.net:/var/www/download
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-testing.msi rsync://veselin@bitpie.net/download
popd
REM ssh veselin@bitpie.net "chmod u+x /var/www/download/bitpie-testing.msi"

@echo.
@echo [ DONE ]
@echo.

pause
