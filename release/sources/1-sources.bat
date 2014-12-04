@echo off


@echo [ run "python setup.py sdist" ]
rm -rf bitpie.tar.gz
cd workspace
rm -rf dist
python setup.py sdist >../sdist.log
cp dist/*.zip ..
rm -rf dist
cd ..

@echo [ archive DONE ]

pause