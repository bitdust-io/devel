@echo off

@echo.
@echo [ upload bitpie-testing.zip to bitpie.net ]
rm -rf bitpie-testing.zip
rename bitpie.zip bitpie-testing.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-testing.zip rsync://veselin@bitpie.net/download


@echo.
@echo [ DONE ]
@echo.

pause
