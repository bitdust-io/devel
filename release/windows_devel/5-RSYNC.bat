@echo off


@echo.
@echo [ turn OFF repository on http://bitdust.io/repo/devel ]
ssh veselin@bitdust.io "rm -f /var/www/repo/devel/checksum"


@echo.
@echo [ run rsync to copy binary files from test to devel repo ]
ssh veselin@bitdust.io "rsync -rptgoE --delete --force -h --progress -vv --stats -c repo/test/* repo/devel/"


@echo.
@echo [ devel repository UPDATED ]


pause
