@echo off

@echo.
@echo [ upload bitdust-development.zip to bitdust.io ]
rm -rf bitdust-development.zip
rename bitdust.zip bitdust-development.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-development.zip rsync://veselin@bitdust.io/download


@echo.
@echo [ DONE ]
@echo.

pause
