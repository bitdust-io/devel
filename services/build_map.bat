@echo off
python build_area.py html_src/services_png_1.htm
python -c "s=open('map.template').read();s=s.replace('{area}',open('area').read());open('map.html','w').write(s);"
mv html_src/services_png_1.png services.png 
rm -rf html_src/*
pause
