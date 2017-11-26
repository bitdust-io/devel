@echo off

@echo.
@echo [ upload bitdust-testing.zip to bitdust.io ]
rm -rf bitdust-testing.zip
rename bitdust.zip bitdust-testing.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-testing.zip rsync://veselin@bitdust.io/download


@echo.
@echo [ DONE ]
@echo.

pause
