@echo off

SETLOCAL ENABLEDELAYEDEXPANSION

for %%i in (*.md) DO (
    set fmd=%%i
    set fhtml=!fmd:~0,-3!.html
    @echo !fhtml! 
    python -m markdown !fmd! > !fhtml!
    python utf8_to_ansi.py !fhtml! !fhtml!
    python fix_html.py !fhtml! !fhtml! styles.css    
)

python build_html.py services
python build_html.py p2p

cp ../services/services.pdf .

pause