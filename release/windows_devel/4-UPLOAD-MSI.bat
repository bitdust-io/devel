
@echo off

@echo.
@echo [ upload bitdust-development.msi to bitdust.io ]
pushd advinstaller\output\
rename bitdust.msi bitdust-development.msi
rsync -rptgoE --force -z --compress-level=9 -h --progress -vv --stats -c bitdust-development.msi rsync://veselin@bitdust.io/download
popd

@echo.
@echo [ DONE ]
@echo.

pause
