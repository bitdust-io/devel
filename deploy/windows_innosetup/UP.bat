@echo off

cd dist
rsync -e ssh -rptgoE --force -z --compress-level=9 -h --progress -v --stats -c bitdust-setup.exe bitdust.io:/var/www/download

@echo.
@echo [ build DONE ]
@echo.

pause