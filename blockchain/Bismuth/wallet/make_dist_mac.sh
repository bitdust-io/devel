#!/usr/bin/env bash
cp wallet.py TornadoBismuthWallet.py
# pyinstaller --hidden-import tornado.locale --hidden-import aiohttp --hidden-import requests_oauth2 --hidden-import six --onefile --icon=favicon.ico TornadoBismuthWallet.py
pyinstaller --hidden-import requests_oauth2 --hidden-import oauthlib --hidden-import tornado.locale --hidden-import aiohttp --hidden-import teslapy --hidden-import bismuthsimpleasset --hidden-import mypolyfit --hidden-import phoneapihandler --hidden-import rainflow --hidden-import testlaapihandler --hidden-import six --onefile --icon=favicon.ico TornadoBismuthWallet.py

cp -R locale dist/locale
cp -R crystals dist/crystals
cp -R modules dist/modules
cp -R crystals.available dist/crystals.available
mkdir dist/themes
cp -R themes/material dist/themes/material
cp -R themes/common dist/themes/common
cp -R themes/mobile dist/themes/mobile
cp -R themes/raw dist/themes/raw
rm TornadoBismuthWallet.py

# Compilation of TornadoWallet on MAC OSX
# Install XCode and XCode Command Line Tools first
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
# brew install pyenv
# echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.bash_profile
# exec "$SHELL"
# env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.7.7
# pyenv local 3.7.7
# git clone https://github.com/Bismuthfoundation/TornadoWallet.git
# cd TornadoWallet
# pip install -r requirements.txt
# pip install pyinstaller
# cd wallet
# ./make_dist_mac.sh
