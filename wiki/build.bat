@echo off
python build_area.py ../services/html_src/services_png_1.htm
python -c "s=open('map.template').read();s=s.replace('{area}',open('area').read());open('map.html','w').write(s);"
rm -rf ../services/html_src/*
pause
