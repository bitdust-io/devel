# BitDust

[bitdust.io](https://bitdust.io)

[![Regression Test](https://github.com/bitdust-io/devel/actions/workflows/pull_request.yml/badge.svg)](https://github.com/bitdust-io/devel/actions/workflows/pull_request.yml)

[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)

[![CodeTriage](https://www.codetriage.com/bitdust-io/devel/badges/users.svg)](https://www.codetriage.com)



## About

#### BitDust is a peer-to-peer online backup utility.

This is a distributed network for backup data storage. Each network participant provides a portion of their hard drive for other users. In exchange, they can store data on other peers.

The redundancy in backup makes it so that if someone loses your data, you can rebuild what was lost and give it to someone else to hold. And all of this happens without you having to do a thing - the software keeps your data safe.

All your data is encrypted before it leaves your computer with a private key your computer generates. No one else can read your data, even BitDust Team! Recovering data is only one way - download the necessary pieces from the computers of other peers and decrypt them with your private key.

BitDust is written in Python using a pure Twisted framework and published under GNU AGPLv3.


#### Current status

The current project stage is about only research opportunities for building a holistic eco-system that protects your privacy in the network by establishing p2p communications of users and maximizing the distribution of information flows in the network.

Currently, a very limited alpha version of the BitDust software exists. We decided to publish those earlier works to verify/test/share our ideas and experiments with other people.


## Install BitDust software

#### Install software dependencies

Seems like in Ubuntu (probably most other distros) you can install all dependencies in that way:

        sudo apt-get install git gcc python3-dev python3-virtualenv


Optionally, you can also install [miniupnpc](http://miniupnp.tuxfamily.org/) tool if you want BitDust automatically deal with UPnPc configuration of your network router so it can also accept incoming connections from other nodes.:

        sudo apt-get install miniupnpc


On MacOSX platform you can install requirements in that way:

        brew install git python3


And use pip to get all required packages:

        pip install --upgrade --user
        pip install --upgrade pip --user
        pip install virtualenv --user


On Raspberry PI you will need to install those packages:

        sudo apt-get install git gcc python3-dev python3-virtualenv libffi-dev libssl-dev



#### Get BitDust to your local machine

Second step is to get the BitDust sources. To have a full control over BitDust process running on your local machine you better make a fork of the Public BitDist repository on GitHub at https://github.com/bitdust-io/public and clone it on your local machine:

        git clone https://github.com/<your GitHub username>/<name of BitDust fork>.git bitdust


The software will periodically run `git fetch` and `git rebase` to check for recent commits in the repo. This way, we ensure that everyone is running the program's latest version. Once you make a fork, you must manually update your Fork and pull commits from the Public BitDust repository if you trust them.

However, if you just trust BitDust contributors, you can simply clone the Public repository directly, and software will be up to date with the "official" public code base:

        git clone https://github.com/bitdust-io/public.git bitdust



#### Building virtual environment

Then you need to build virtual environment with all required Python dependencies, BitDust software will run fully isolated.

Single command should make it for you, all required files will be generated in `~/.bitdust/venv/` sub-folder:

        cd bitdust
        python3 bitdust.py install


The last step to prepare your BitDust software is to make a short alias in your OS. Then you can type bitdust in the command line to speed up the program access:

        sudo ln -s -f /home/<user>/.bitdust/bitdust /usr/local/bin/bitdust



#### Run BitDust

Start using the software by creating an identity for your device in BitDust network:

        bitdust id create <some nick name>


I recommend you to create another copy of your Private Key in a safe place to be able to recover your data in the future. You can do it with such command:

        bitdust key copy <nickname>.bitdust.key


Your settings and local files are located in that folder: `~/.bitdust`

Type this command to read more info about BitDust commands:

        bitdust help


To run the software just type:

        bitdust


Start as background process:

        bitdust daemon


To get some more insights or just to know how to start playing with software
you can visit [BitDust Commands](https://bitdust.io/wiki/commands.html) page.

To get more info about API methods available go to [BitDust API](https://bitdust.io/wiki/api.html) page.



#### Binary Dependencies

If you are installing BitDust on Windows platforms, you may require some binary packages already compiled and packaged for Microsoft Windows platforms. You can check the following locations and download needed binaries and libraries:

* cygwin: [cygwin.com](https://cygwin.com/install.html)
* git: [git-scm.com](https://git-scm.com/download/win)
* python2.7 or python3: [python.org](http://python.org/download/releases)
* twisted: [twistedmatrix.com](http://twistedmatrix.com)
* pyasn1: [pyasn1.sourceforge.net](http://pyasn1.sourceforge.net)
* miniupnpc: [miniupnp.tuxfamily.org](http://miniupnp.tuxfamily.org/)



#### Docker Hub container image

You can also run BitDust inside Docker. We prepared a container that has BitDust installed and is easy to run. You will have to SSH into the running container after starting it and manually configure BitDust as you wish and run it:

        docker run -d -P --name bdnode bitdust/app1
        docker port bdnode 22
        0.0.0.0:32771  <-  learn which SSH port was opened on your host


Now you can ssh to the container, password is `bitdust`:

        ssh root@localhost -p 32771
        password: bitdust


Inside the container you will have BitDust installed and ready to use, so you can run it directly:

        root@1ef6a46c3042:~# bitdust



## Feedback

You can contact [BitDust contributors](https://github.com/bitdust-io) on GitHub if you have any questions or ideas.
Welcome to the future!
