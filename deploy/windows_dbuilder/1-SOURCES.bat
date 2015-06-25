@echo off


@echo.
@echo [ build sources ]
SET curpath=%cd%
pushd ..\sources
rm -rf workspace
call 0-build.bat


