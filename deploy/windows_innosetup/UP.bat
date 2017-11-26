@echo off

cd dist
rsync -e ssh -rptgoE -p --force -z --compress-level=9 -h --progress -v --stats -c bitdust-setup.exe bitdust.io:/var/www/download
ssh bitdust.io "chmod +r /var/www/download/bitdust-setup.exe"

@echo.
@echo [ build DONE ]
@echo.

pause