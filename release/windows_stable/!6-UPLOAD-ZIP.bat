@echo off

@echo.
@echo [ upload bitpie-stable.zip to bitpie.net ]
rm -rf bitpie-stable.zip
rename bitpie.zip bitpie-stable.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitpie-stable.zip rsync://veselin@bitpie.net/download


@echo.
@echo [ DONE ]
@echo.

pause
