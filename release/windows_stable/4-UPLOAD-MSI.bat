
@echo off

@echo.
@echo [ upload bitdust-stable.msi to bitdust.io ]
pushd advinstaller\output\
if exist bitdust.msi rename bitdust.msi bitdust-stable.msi
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-stable.msi rsync://veselin@bitdust.io/download
popd

@echo.
@echo [ DONE ]
@echo.

pause
