
@echo off

@echo.
@echo [ upload bitpie-development.msi to bitpie.net ]
pushd advinstaller\output\
rename bitpie.msi bitpie-development.msi
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-development.msi rsync://veselin@bitpie.net/download
popd

@echo.
@echo [ DONE ]
@echo.

pause
