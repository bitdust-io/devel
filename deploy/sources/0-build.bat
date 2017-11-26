@echo off


set CURRENT_PATH=%cd%


@echo.
@echo [ prepare workspace folder in %CURRENT_PATH%\workspace ]
rm -rf workspace
mkdir workspace
mkdir workspace\bitdust
cp MANIFEST.in workspace


@echo.
@echo [ export from git repo into workspace ]
pushd ..\.. 
git archive master > %CURRENT_PATH%\workspace\bitdust\master.tar
popd 
pushd workspace\bitdust
tar xf master.tar
rm master.tar
popd


@echo.
@echo [ prepare setup.py file ]
cp setup.py workspace
python -c "v=open('../version').read().strip(); s=open('workspace/setup.py').read(); s=s.replace('{version}', v); open('workspace/setup.py', 'w').write(s);"


@echo.
@echo [ remove some files ]
pushd workspace\bitdust
rm commit.bat
rm import.bat
rm commit.sh
rm export.sh
rm -rf release
rm -rf screenshots
rm -rf scripts
rm -rf tests
rm -rf deploy\windows\Python2.7.9


@echo.
@echo [ move some files to the top level ]
mv -v *.txt ..

popd


@echo.
@echo [ sources DONE ]
pause