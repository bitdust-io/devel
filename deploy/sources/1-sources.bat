@echo off


@echo.
@echo [ run "python setup.py sdist" ]
rm -rf bitdust.tar.gz
cd workspace
rm -rf dist
python setup.py sdist >../sdist.log
cp dist/*.zip ..
rm -rf dist
cd ..

@echo.
@echo [ archive DONE ]

pause