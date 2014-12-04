@echo off


@echo [ build area ]
python build_area.py ../services/html_src/services_png_1.htm


@echo [ create "map.html" ]
python -c "s=open('map.template').read();s=s.replace('{area}',open('area').read());open('map.html','w').write(s);"
cp ../services/html_src/services_png_1.png services.png 


rem @ echo [ erase "html_src" folder ]
rem rm -rf ../services/html_src/*


@echo [ DONE ]

pause
