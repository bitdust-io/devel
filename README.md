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

http://bitdust.io



## Install

Seems like in Ubuntu (probably most other distros) you just need to install all dependencies at first step:

        sudo apt-get install git python-twisted python-setuptools python-pip
        pip install Django==1.7 pycrypto psutil 
    
Optionally, you can also install [miniupnpc](http://miniupnp.tuxfamily.org/) tool if you want BitDust automatically deal with UPnPc configuration of your network router so it can also accept incomming connections from other nodes.:

        sudo apt-get install miniupnpc


Get Sources:

        git clone http://gitlab.bitdust.io/devel/bitdust.git


Create an alias in OS so you can easily run the program from any location:

        cd bitdust
        python bitdust.py alias > /usr/local/bin/bitdust
        chmod +x /usr/local/bin/bitdust
        

Create an identity for you in the BitDust network:
       
        bitdust id create <some nick name>
       

I recommend you to create another copy of your Private Key in a safe place to be able to recover your data in the future. You can do it with such command:

        bitdust key copy <filename>


Your settings and local files are located in that folder: ~/.bitdust.

Type this command to read more info about BitDust commands:

        bitdust help


Please read more about [BitDust Commands](commands.md) to start playing with software.


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
