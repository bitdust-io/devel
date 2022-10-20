from setuptools import setup

setup(
    **{
        'author':
        'Veselin Penev',
        'author_email':
        'bitdust.io@gmail.com',
        'classifiers': [
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'Environment :: No Input/Output (Daemon)',
            'Framework :: Twisted',
            'Intended Audience :: Developers',
            'Intended Audience :: End Users/Desktop',
            'Intended Audience :: Information Technology',
            'Intended Audience :: Science/Research',
            'Intended Audience :: Telecommunications Industry',
            'License :: OSI Approved :: GNU Affero General Public License '
            'v3 or later (AGPLv3+)',
            'Natural Language :: English',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.6',
            'Topic :: Communications :: Chat',
            'Topic :: Internet :: WWW/HTTP',
            'Topic :: Communications :: File Sharing',
            'Topic :: Desktop Environment :: File Managers',
            'Topic :: Internet :: File Transfer Protocol (FTP)',
            'Topic :: Security :: Cryptography',
            'Topic :: System :: Archiving :: Backup',
            'Topic :: System :: Distributed Computing',
            'Topic :: System :: Filesystems',
            'Topic :: System :: System Shells',
            'Topic :: Utilities',
        ],
        'description':
        'BitDust is a decentralized on-line storage network for safe, '
        'independent and private communications.',
        'include_package_data':
        True,
        'install_requires': ['twisted', 'service_identity', 'pycryptodomex', 'pyparsing', 'appdirs', 'psutil', 'cffi', 'six'],
        'license':
        'GNU Affero General Public License v3 or later (AGPLv3+)',
        'long_description':
        '# BitDust\n'
        '\n'
        '[bitdust.io](https://bitdust.io)\n'
        '\n'
        '[![Build '
        'Status](https://travis-ci.com/bitdust-io/devel.svg?branch=master)](https://travis-ci.com/bitdust-io/devel)\n'
        '\n'
        '\n'
        '## About\n'
        '\n'
        '#### BitDust is a peer-to-peer online backup utility.\n'
        '\n'
        'This is a distributed network for backup data storage. '
        'Each participant of the network provides a portion of '
        'his hard drive for other users. In exchange, he is able '
        'to store his data on other peers.\n'
        '\n'
        'The redundancy in backup makes it so if someone loses '
        'your data, you can rebuild what was lost and give it to '
        'someone else to hold. And all of this happens without '
        'you having to do a thing - the software keeps your data '
        'in safe.\n'
        '\n'
        'All your data is encrypted before it leaves your '
        'computer with a private key your computer generates. No '
        'one else can read your data, even BitDust Team! Recover '
        'data is only one way - download the necessary pieces '
        'from computers of other peers and decrypt them with your '
        'private key.\n'
        '\n'
        'BitDust is written in Python using pure Twisted '
        'framework and published under GNU AGPLv3.\n'
        '\n'
        '\n'
        '#### Current status\n'
        '\n'
        'Current project stage is about to only research '
        'opportunities of\n'
        'building a holistic eco-system that protects your '
        'privacy in the network\n'
        'by establishing p2p communications of users and maximize '
        'distribution of\n'
        'information flows in the network.\n'
        '\n'
        'At the moment exists a very limited alpha version of the '
        'BitDust software.\n'
        'We decided to publish those earlier works to '
        'verify/test/share our ideas and experiments with other '
        'people.\n'
        '\n'
        '\n'
        '## Install BitDust software\n'
        '\n'
        '#### Install software dependencies\n'
        '\n'
        'Seems like in Ubuntu (probably most other distros) you '
        'can install all dependencies in that way:\n'
        '\n'
        '        sudo apt-get install git gcc python3-dev '
        'python3-virtualenv\n'
        '\n'
        '\n'
        'Optionally, you can also install '
        '[miniupnpc](http://miniupnp.tuxfamily.org/) tool if you '
        'want BitDust automatically deal with UPnPc configuration '
        'of your network router so it can also accept incomming '
        'connections from other nodes.:\n'
        '\n'
        '        sudo apt-get install miniupnpc\n'
        '\n'
        '\n'
        'On MacOSX platform you can install requirements in that '
        'way:\n'
        '\n'
        '        brew install git python3\n'
        '\n'
        '\n'
        'And use pip to get all required packages:\n'
        '\n'
        '        pip install --upgrade --user\n'
        '        pip install --upgrade pip --user\n'
        '        pip install virtualenv --user\n'
        '\n'
        '\n'
        'On Raspberry PI you will need to install those '
        'packages:\n'
        '\n'
        '        sudo apt-get install git gcc python3-dev '
        'python3-virtualenv libffi-dev libssl-dev\n'
        '\n'
        '\n'
        '\n'
        '#### Get BitDust to your local machine\n'
        '\n'
        'Second step is to get the BitDust sources. To have a '
        'full control over BitDust process running on your local '
        'machine you better make a fork of the Public BitDist '
        'repository on GitHub at '
        'https://github.com/bitdust-io/public and clone it on '
        'your local machine:\n'
        '\n'
        '        git clone https://github.com/<your GitHub '
        'username>/<name of BitDust fork>.git bitdust\n'
        '\n'
        '\n'
        'The software will periodically run `git fetch` and `git '
        'rebase` to check for recent commits in the repo. This '
        'way we make sure that everyone is running the latest '
        'version of the program. Once you made a fork, you will '
        'have to update your Fork manually and pull commits from '
        'Public BitDust repository if you trust them.\n'
        '\n'
        'However if you just trust BitDust contributors you can '
        'simply clone the Public repository directly and software '
        'will be up to date with the "official" public code '
        'base:\n'
        '\n'
        '        git clone '
        'https://github.com/bitdust-io/public.git bitdust\n'
        '\n'
        '\n'
        '\n'
        '#### Building virtual environment\n'
        '\n'
        'Then you need to build virtual environment with all '
        'required Python dependencies, BitDust software will run '
        'fully isolated.\n'
        '\n'
        'Single command should make it for you, all required '
        'files will be generated in `~/.bitdust/venv/` '
        'sub-folder:\n'
        '\n'
        '        cd bitdust\n'
        '        python3 bitdust.py install\n'
        '\n'
        '\n'
        'Last step to make BitDust software ready is to make a '
        'short alias in your OS, then you can just type `bitdust` '
        'in command line to fast access the program:\n'
        '        \n'
        '        sudo ln -s -f /home/<user>/.bitdust/bitdust '
        '/usr/local/bin/bitdust\n'
        '        \n'
        '\n'
        '\n'
        '#### Run BitDust\n'
        '\n'
        'Start using the software by creating an identity for '
        'your device in BitDust network:\n'
        '       \n'
        '        bitdust id create <some nick name>\n'
        '       \n'
        '\n'
        'I recommend you to create another copy of your Private '
        'Key in a safe place to be able to recover your data in '
        'the future. You can do it with such command:\n'
        '\n'
        '        bitdust key copy <nickname>.bitdust.key\n'
        '\n'
        '\n'
        'Your settings and local files are located in that '
        'folder: ~/.bitdust\n'
        '\n'
        'Type this command to read more info about BitDust '
        'commands:\n'
        '\n'
        '        bitdust help\n'
        '\n'
        '\n'
        'To run the software just type:\n'
        '\n'
        '        bitdust\n'
        '        \n'
        '\n'
        'Start as background process:\n'
        '\n'
        '        bitdust daemon\n'
        '\n'
        '\n'
        'To get some more insights or just to know how to start '
        'playing with software\n'
        'you can visit [BitDust '
        'Commands](https://bitdust.io/commands.html) page. \n'
        '\n'
        'To get more info about API methods available go to '
        '[BitDust API](https://bitdust.io/api.html) page.\n'
        '\n'
        '\n'
        '\n'
        '#### Binary Dependencies\n'
        '\n'
        'If you are installing BitDust on Windows platforms, you '
        'may require some binary packages already compiled and '
        'packaged for Microsoft Windows platforms, you can check '
        'following locations and download needed binaries and '
        'libraries:\n'
        '\n'
        '* cygwin: [cygwin.com](https://cygwin.com/install.html)\n'
        '* git: [git-scm.com](https://git-scm.com/download/win)\n'
        '* python2.7 or python3: '
        '[python.org](http://python.org/download/releases)\n'
        '* twisted: '
        '[twistedmatrix.com](http://twistedmatrix.com)\n'
        '* pyasn1: '
        '[pyasn1.sourceforge.net](http://pyasn1.sourceforge.net)\n'
        '* miniupnpc: '
        '[miniupnp.tuxfamily.org](http://miniupnp.tuxfamily.org/)\n'
        '\n'
        '\n'
        '## Feedback\n'
        '\n'
        'You can contact [BitDust '
        'contributors](https://github.com/bitdust-io) on GitHub '
        'if you have any questions or ideas.\n'
        'Welcome to the future!\n'
        '\n',
        'name':
        'bitdust',
        'packages': [
            'bitdust',
            'bitdust_forks',
        ],
        'tests_require': [],
        'url':
        'https://github.com/bitdust-io/public.git',
        'version':
        '0.0.1',
        'zip_safe':
        False,
    }
)
