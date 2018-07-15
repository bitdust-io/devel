#/bin/sh

virtualenv -p python2.7 venv

venv/bin/python --version

source venv/bin/activate

git clone https://github.com/ethereum/pyethapp.git

cd pyethapp/

pip install setuptools==37

pip install -r requirements.txt

python setup.py install

USE_PYETHEREUM_DEVELOP=1 python setup.py develop

