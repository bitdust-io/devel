# BitDust
[bitdust.io](http://bitdust.io)


## English
* [Main web site](http://bitdust.io/toc.html)
* [Public Git repository](http://gitlab.bitdust.io/devel/bitdust.docs.english/blob/master/README.md)
* [Mirror in GitHub repository](http://gitlab.bitdust.io/devel/bitdust.docs.english/blob/master/README.md)


## Russian

* [Main web site](http://ru.bitdust.io/toc.html)
* [Mirror in Public Git repository](http://gitlab.bitdust.io/devel/bitdust.docs/blob/master/README.md)



## About

#### BitDust is a peer-to-peer online backup utility.

This is a distributed network for backup data storage. Each participant of the network provides a portion of his hard drive for other users. In exchange, he is able to store his data on other peers.

The redundancy in backup makes it so if someone loses your data, you can rebuild what was lost and give it to someone else to hold. And all of this happens without you having to do a thing - the software keeps your data in safe.

All your data is encrypted before it leaves your computer with a private key your computer generates. No one else can read your data, even BitDust Team! Recover data is only one way - download the necessary pieces from computers of other peers and decrypt them with your private key.

BitDust is written in Python using pure Twisted framework and published under GNU AGPLv3.



## Install


### Get the software

Seems like in Ubuntu (probably most other distros) you can install all dependencies in that way:

        sudo apt-get install git python-dev python-setuptools python-pip python-virtualenv
        
        sudo apt-get install python-twisted python-django python-crypto python-pyasn1 python-psutil libffi-dev


Optionally, you can also install [miniupnpc](http://miniupnp.tuxfamily.org/) tool if you want BitDust automatically deal with UPnPc configuration of your network router so it can also accept incomming connections from other nodes.:

        sudo apt-get install miniupnpc


Second step is to get the BitDust sources:

        git clone http://gitlab.bitdust.io/stable/bitdust.latest.git bitdust


Then you need to build virtual environment with all required Python dependencies, BitDust software will run fully isolated.
Single command should make it for you, all required files will be generated in `~/.bitdust/venv/` sub-folder:

        cd bitdust
        python bitdust.py install


Last step to make BitDist software ready is to make a short alias in your OS, then just type `bitdust` in command line to access the program:
        
        sudo ln -s /home/<user>/.bitdust/bitdust /usr/local/bin/bitdust
        


### Run BitDist

Start using the software by creating an identity for your device in BitDust network:
       
        bitdust id create <some nick name>
       

I recommend you to create another copy of your Private Key in a safe place to be able to recover your data in the future. You can do it with such command:

        bitdust key copy <nickname>.bitdust.key


Your settings and local files are located in that folder: ~/.bitdust

Type this command to read more info about BitDust commands:

        bitdust help


To run the software type:

        bitdust
        

Start as background process:

        bitdust detach


To get some more insights or just to know how to start playing with software
you can visit [BitDust Commands](https://bitdust.io/commands.html) page. 



## Dependencies

python 2.6 or 2.7, python3 is not supported
    http://python.org/download/releases
    
twisted 11.0 or higher: 
    http://twistedmatrix.com
    
pyasn1: 
    http://pyasn1.sourceforge.net
    
pyOpenSSL: 
    https://launchpad.net/pyopenssl
    
pycrypto: 
    https://www.dlitz.net/software/pycrypto/

wxgtk2.8: 
    http://wiki.wxpython.org/InstallingOnUbuntuOrDebian

miniupnpc:
    http://miniupnp.tuxfamily.org/
