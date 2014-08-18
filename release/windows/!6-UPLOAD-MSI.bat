@echo off

@echo.
@echo [ upload bitpie-testing.msi to bitpie.net ]
pushd advinstaller\output\
rename bitpie.msi bitpie-testing.msi
scp bitpie-testing.msi veselin@bitpie.net:/var/www/download
popd
REM ssh veselin@bitpie.net "chmod u+x /var/www/download/bitpie-testing.msi"

@echo.
@echo [ DONE ]
@echo.

pause
