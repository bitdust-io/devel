@echo off


@echo.
@echo [ turn OFF repository on http://bitdust.io/repo/stable ]
ssh veselin@bitdust.io "rm -f /var/www/repo/stable/checksum"


@echo.
@echo [ run rsync to copy binary files from devel to stable repo ]
ssh veselin@bitdust.io "rsync -rptgoE --delete --force -h --progress -vv --stats -c repo/devel/* repo/stable/"


@echo.
@echo [ stable repository UPDATED ]

  
pause