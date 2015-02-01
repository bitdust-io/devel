@echo off
setx /M PATH "PATH;%USERPROFILE%\.bitdust\bin\"
START cmd /k "cd %USERPROFILE%\.bitdust\bin\ & echo Welcome to BitDust project! & echo Run `bitdust register your_nick_name` & echo Type `bitdust usage` to list all available commands and options."
bitdust