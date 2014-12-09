
@echo off

@echo.
@echo [ upload bitpie-stable.msi to bitpie.net ]
pushd advinstaller\output\
if exist bitpie.msi rename bitpie.msi bitpie-stable.msi
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-stable.msi rsync://veselin@bitpie.net/download
popd

@echo.
@echo [ DONE ]
@echo.

pause
