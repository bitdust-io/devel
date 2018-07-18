#/bin/sh

ROOT_DIR="$HOME/.bitdust"
BLOCKCHAIN_DIR="${ROOT_DIR}/blockchain"
BLOCKCHAIN_SRC="${BLOCKCHAIN_DIR}/src"
BLOCKCHAIN_DATA="${BLOCKCHAIN_DIR}/data"
BLOCKCHAIN_VENV="${BLOCKCHAIN_SRC}/venv"
BLOCKCHAIN_PYTHON="${BLOCKCHAIN_VENV}/bin/python3.6"
BLOCKCHAIN_VIRTUALENV="${BLOCKCHAIN_DIR}/virtualenv"
BLOCKCHAIN_VIRTUALENV_BIN="${BLOCKCHAIN_VIRTUALENV}/bin/virtualenv"


if ! [ -x "$(command -v python3.6)" ]; then
    echo ''
    echo '##### DEPLOYMENT FAILED! Python 3.6 development version is required but not installed!'
    echo ''
    echo 'You can install it this way:'
    echo '    sudo add-apt-repository ppa:deadsnakes/ppa'
    echo '    sudo apt-get update'
    echo '    sudo apt-get install python3.6-dev'
    echo ''
    exit 1
else
    echo ''
    echo '##### Python 3.6 is already installed'
fi


if ! [ -x "$(command -v pip3)" ]; then
    echo ''
    echo '##### DEPLOYMENT FAILED! Pip3 is required but not installed!'
    echo ''
    echo 'You can install it this way:'
    echo '    sudo apt-get install python3-pip'
    echo ''
    exit 1
else
    echo ''
    echo '##### Pip3 is already installed'
fi


if ! [ -f $BLOCKCHAIN_VIRTUALENV/bin/virtualenv ]; then
    echo ''
    echo '##### Installing isolated virtualenv'
    PYTHONUSERBASE=$BLOCKCHAIN_VIRTUALENV pip3 install --ignore-installed --user virtualenv
else
    echo ''
    echo '##### Found isolated virtualenv binaries'
fi


if [ ! -d $BLOCKCHAIN_DIR ]; then
    mkdir -p $BLOCKCHAIN_DIR
    mkdir -p $BLOCKCHAIN_DATA
    mkdir -p $BLOCKCHAIN_DATA/logs
    mkdir -p $BLOCKCHAIN_VIRTUALENV
    echo '' > $BLOCKCHAIN_DATA/logs/trinity.log
    echo ''
    echo "##### Created required folders for Py-EVM Blockchain in ${BLOCKCHAIN_DIR}"
fi


if ! [ -f $BLOCKCHAIN_SRC/setup.py ]; then
    echo ''
    echo '##### Cloning Py-EVM repository'
    git clone --depth=1 https://github.com/vesellov/py-evm.git $BLOCKCHAIN_SRC
else
    echo ''
    echo '##### Updating the source code of Py-EVM'
    cd $BLOCKCHAIN_SRC
    git fetch
    git reset --hard origin/master
    cd $OLDPWD
fi


if [ ! -d $BLOCKCHAIN_VENV ]; then
    echo ''
    echo '##### Building Py-EVM virtual environment'
    PYTHONUSERBASE=$BLOCKCHAIN_VIRTUALENV $BLOCKCHAIN_VIRTUALENV_BIN -p python3.6 $BLOCKCHAIN_VENV
fi


if [ ! -f $BLOCKCHAIN_VENV/bin/pip ]; then
    echo ''
    echo '##### Pip is not found inside virtual environment, rebuilding'
    rm -rf $BLOCKCHAIN_VENV
    PYTHONUSERBASE=$BLOCKCHAIN_VIRTUALENV $BLOCKCHAIN_VIRTUALENV_BIN -p python3.6 $BLOCKCHAIN_VENV
fi


echo ''
echo '##### Installing/Updating trinity with pip'
cd $BLOCKCHAIN_SRC
$BLOCKCHAIN_PYTHON setup.py install


echo ''
echo 'To start trinity process you can run via command line:'
echo ''
echo "${BLOCKCHAIN_VENV}/bin/trinity --data-dir=${BLOCKCHAIN_DATA} --port=30345"


echo ''
echo ''
echo 'DONE!'
echo ''
