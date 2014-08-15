@echo off

@echo.
@echo [ upload datahaven-testing.msi to datahaven.net ]
mv advinstaller/output/datahaven.msi advinstaller/output/datahaven-testing.msi
pscp advinstaller/output/datahaven-testing.msi datahaven.net:/var/www/
ssh veselinux@datahaven.net "cd /var/www; chmod u+x datahaven-testing.msi;"

@echo.
@echo [ DONE ]
@echo.

pause
