@echo off

@echo [ prepare workspace folder ]
rm -rf workspace
mkdir workspace
mkdir workspace\bitdust
cp MANIFEST.in workspace

@echo [ export from git repo into workspace ]
pushd ..\.. 
git archive master > release\sources\workspace\bitdust\master.tar
popd 
pushd workspace\bitdust
tar xf master.tar
rm master.tar
popd

@echo [ prepare setup.py file ]
cp setup.py workspace
python -c "v=open('../version').read().strip(); s=open('workspace/setup.py').read(); s=s.replace('{version}', v); open('workspace/setup.py', 'w').write(s);"

@echo [ remove some files ]
pushd workspace\bitdust
rm commit.bat
rm commit.sh
rm -rf screenshots\*.*
rm -rf release\*.*

@echo [ move some files to the top level ]
mv -v *.txt ..

popd

@echo [ sources done ]
pause