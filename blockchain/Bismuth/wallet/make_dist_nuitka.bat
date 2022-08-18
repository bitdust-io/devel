del /f /s /q dist 1>nul
rmdir /s /q dist
del /f /s /q build 1>nul
rmdir /s /q build

copy wallet.py TornadoBismuthWallet.py
robocopy . TornadoBismuthWallet.build favicon.ico
python -m nuitka --follow-imports TornadoBismuthWallet.py --standalone --show-progress -j 8 --recurse-all --windows-icon=favicon.ico
ren TornadoBismuthWallet.dist dist
ren TornadoBismuthWallet.build build
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
