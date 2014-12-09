@echo off


@echo.
@echo [ turn OFF repository on http://bitpie.net/repo/stable ]
ssh veselin@bitpie.net "rm -f /var/www/repo/stable/checksum"


@echo.
@echo [ run rsync to copy binary files from devel to stable repo ]
ssh veselin@bitpie.net "rsync -rptgoE --delete --force -h --progress -vv --stats -c repo/devel/* repo/stable/"


@echo.
@echo [ stable repository UPDATED ]

  
pause