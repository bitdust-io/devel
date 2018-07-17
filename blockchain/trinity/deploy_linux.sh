#/bin/sh

ROOT_DIR="$HOME/.bitdust"
TRINITY_DIR="${ROOT_DIR}/trinity"
TRINITY_VENV="${TRINITY_DIR}/venv"
TRINITY_BIN="${TRINITY_DIR}/bin/"
TRINITY_VIRTUALENV="${TRINITY_DIR}/bin/virtualenv"


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


if [ ! -d $TRINITY_DIR ]; then
    mkdir -p $TRINITY_DIR
    mkdir -p $TRINITY_DIR/bin
    echo ''
    echo '##### Created folder for Trinity Blockchain'
fi


if ! [ -f $TRINITY_VIRTUALENV/bin/virtualenv ]; then
    echo ''
    echo '##### Installing isolated virtualenv'
    PYTHONUSERBASE=TRINITY_VIRTUALENV pip3 install --ignore-installed --user virtualenv
else
    echo ''
    echo '##### Found isolated virtualenv binaries'
fi


if [ ! -d $TRINITY_VENV ]; then
    echo ''
    echo '##### Building Trinity virtual environment'
    $TRINITY_VIRTUALENV/bin/virtualenv -p python3.6 $TRINITY_VENV
fi


if [ ! -f $TRINITY_VENV/bin/pip ]; then
    echo ''
    echo '##### Pip is not found inside virtual environment, rebuilding'
    rm -rf $TRINITY_VENV
    $TRINITY_VIRTUALENV/bin/virtualenv -p python3.6 $TRINITY_VENV
fi


echo ''
echo '##### Installing/Updating trinity with pip'
echo ''
$TRINITY_VENV/bin/pip install -U trinity


echo ''
echo 'DONE!'
echo ''
