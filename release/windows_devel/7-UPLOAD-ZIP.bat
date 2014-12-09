@echo off

@echo.
@echo [ upload bitpie-development.zip to bitpie.net ]
rm -rf bitpie-development.zip
rename bitpie.zip bitpie-development.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-development.zip rsync://veselin@bitpie.net/download


@echo.
@echo [ DONE ]
@echo.

pause
