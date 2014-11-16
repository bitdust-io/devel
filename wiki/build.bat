@echo off
python build_area.py
python -c "s=open('map.template').read();s=s.replace('{area}',open('area').read());open('map.html','w').write(s);"
pause
