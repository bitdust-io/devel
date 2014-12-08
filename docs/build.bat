@echo off

@echo "install.md -> install.html"
python -m markdown install.md > install.html
python utf8_to_ansi.py install.html install.html
python fix_html.py install.html install.html

@echo "concept.md -> concept.html"
python -m markdown concept.md > concept.html
python utf8_to_ansi.py concept.html concept.html
python fix_html.py concept.html concept.html

@echo "README.md -> index.html"
python -m markdown ../README.md > index.html
python utf8_to_ansi.py index.html index.html
python fix_html.py index.html index.html

python build_html.py services
python build_html.py p2p

cp ../services/services.pdf .

pause