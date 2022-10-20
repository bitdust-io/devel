del /f /s /q dist 1>nul
rmdir /s /q dist
del /f /s /q build 1>nul
rmdir /s /q build

copy wallet.py TornadoBismuthWallet.py
pyinstaller --hidden-import requests_oauth2 --hidden-import oauthlib --hidden-import tornado.locale --hidden-import aiohttp --hidden-import teslapy --hidden-import bismuthsimpleasset --hidden-import mypolyfit --hidden-import phoneapihandler --hidden-import rainflow --hidden-import testlaapihandler --hidden-import six --onefile --icon=favicon.ico TornadoBismuthWallet.py

robocopy locale dist/locale /S /E *.mo
mkdir dist/themes
robocopy themes/material dist/themes/material /S /E
robocopy themes/common dist/themes/common /S /E
robocopy crystals dist/crystals /S /E

REM Copy libsecp256k1.dll to dist directory, then
REM in cffi\app.py def _load_backend_lib(backend, name, flags):
REM         if "libsecp256k1" in name:
REM             path = "libsecp256k1.dll"
REM         else:
REM            raise OSError(msg)

REM see https://nsis.sourceforge.io/Main_Page , make installer from zip
REM Or inno setup https://cyrille.rossant.net/create-a-standalone-windows-installer-for-your-python-application/
REM or https://pynsist.readthedocs.io/en/latest/index.html
