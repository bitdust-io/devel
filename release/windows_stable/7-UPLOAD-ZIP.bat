@echo off

@echo.
@echo [ upload bitdust-stable.zip to bitdust.io ]
rm -rf bitdust-stable.zip
rename bitdust.zip bitdust-stable.zip
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-stable.zip rsync://veselin@bitdust.io/download


@echo.
@echo [ DONE ]
@echo.

pause
