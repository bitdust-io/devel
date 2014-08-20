@echo off


@echo.
@echo [ turn OFF repository on http://bitpie.net/repo/devel ]
ssh veselin@bitpie.net "rm -f /var/www/repo/devel/checksum"


@echo.
@echo [ run rsync to copy binary files from test to devel repo ]
ssh veselin@bitpie.net "rsync -rptgoE --delete --force -h --progress -vv --stats -c repo/test/* repo/devel/"


@echo.
@echo [ devel repository UPDATED ]

  
pause