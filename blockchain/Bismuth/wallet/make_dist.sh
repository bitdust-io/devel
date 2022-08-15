#!/usr/bin/env bash
cp wallet.py TornadoBismuthWallet.py
pyinstaller --hidden-import requests_oauth2 --hidden-import oauthlib --hidden-import tornado.locale --hidden-import aiohttp --hidden-import teslapy --hidden-import bismuthsimpleasset --hidden-import mypolyfit --hidden-import phoneapihandler --hidden-import rainflow --hidden-import teslaapihandler --hidden-import six --onefile --icon=favicon.ico TornadoBismuthWallet.py
rm -rd dist/locale
rm -rd dist/themes
rm -rd dist/crystals
cp -r locale dist/
mkdir dist/themes
cp -r themes/material dist/themes/material
cp -r themes/common dist/themes/common
cp -r crystals dist/
rm TornadoBismuthWallet.py

# Compilation of TornadoWallet on Ubuntu 16.04
# sudo apt-get update
# sudo apt-get upgrade
# sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev git
# curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash
# export PATH="~/.pyenv/bin:$PATH"
# eval "$(pyenv init -)"
# eval "$(pyenv virtualenv-init -)"
# env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.7.7
# pyenv local 3.7.7
# git clone https://github.com/Bismuthfoundation/TornadoWallet.git
# cd TornadoWallet
# pip install -r requirements.txt
# pip install pyinstaller
# cd wallet
# ./make_dist.sh
