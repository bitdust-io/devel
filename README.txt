BitPie.NET
=============

BitPie.NET is a peer to peer online backup utility.

This is a distributed network for backup data storage. Each participant of the network provides a portion of his hard drive for other users. In exchange, he is able to store his data on other peers.

The redundancy in backup makes it so if someone loses your data, you can rebuild what was lost and give it to someone else to hold. And all of this happens without you having to do a thing - the software keeps your data in safe.

All your data is encrypted before it leaves your computer with a private key your computer generates. No one else can read your data, even DataHaven.NET! Recover data is only one way - download the necessary pieces from computers of other peers and decrypt them with your private key.

BitPie.NET is written in Python using pure Twisted framework.

http://bitpie.net



Install
=======

Copy folder "bitpie" in any place you want.

To start from command line:

cd bitpie
python bitpie.py show


You will have to create a new "Identity" first.
If you run on a system without graphical interface you need to register from command line:

python bitpie.py register <your_nickname>



Dependencies
============

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
    
PIL: 
    http://www.pythonware.com/products/pil
    
wxgtk2.8: 
    http://wiki.wxpython.org/InstallingOnUbuntuOrDebian


Or just install following packages from repos:
    
python
python-twisted
python-pyasn1
python-openssl
python-crypto
python-wxgtk2.8
python-imaging 

 