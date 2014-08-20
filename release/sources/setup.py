from distutils.core import setup

setup(  name='datahaven',
        version='rev{revision}',
        author='Vincent Cate, DataHaven.NET LTD',
        author_email='datahaven.net@gmail.com',
        maintainer='Veselin Penev',
        maintainer_email='penev.veselin@gmail.com',
        url='http://datahaven.net',
        description='Distributed storage network',
        long_description='''DataHaven.NET - distributed storage network.

This is a distributed network for backup data storage. Each participant of the network provides a portion of his hard drive for other users. In exchange, he is able to store his data on other peers.

The redundancy in backup makes it so if someone loses your data, you can rebuild what was lost and give it to someone else to hold. And all of this happens without you having to do a thing - the software keeps your data in safe.

All your data is encrypted before it leaves your computer with a private key your computer generates. No one else can read your data, even DataHaven.NET! Recover data is only one way - download the necessary pieces from computers of other peers and decrypt them with your private key.

DataHaven.NET is written in Python using pure Twisted framework.        

''',
        download_url='http://datahaven.net',
        #download_url='http://pypi.python.org/packages/source/d/datahaven/datahaven-rev{revision}.tar.gz',
        license='Copyright DataHaven.NET LTD. of Anguilla, 2006,\nAll rights reserved.\nUse of this software constitutes acceptance of the Terms of Use: http://datahaven.net/terms_of_use.html ',
        keywords='''p2p, peer to peer, backup, restore, distributed, cloud, online, storage, data, recover, python, twisted''',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'Environment :: Web Environment',
            'Framework :: Twisted',
            'Intended Audience :: Customer Service',
            'Intended Audience :: Developers',
            'Intended Audience :: End Users/Desktop',
            'Intended Audience :: Information Technology',
            'Intended Audience :: System Administrators',
            'License :: Other/Proprietary License',
            'Natural Language :: English',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: Microsoft :: Windows :: Windows 7',
            'Operating System :: Microsoft :: Windows :: Windows Vista',
            'Operating System :: Microsoft :: Windows :: Windows XP',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Topic :: Security',
            'Topic :: Security :: Cryptography',
            'Topic :: System :: Archiving :: Backup',
            'Topic :: System :: Distributed Computing',
            'Topic :: Utilities',
            ],
            
        packages=[
            'datahaven',
            'datahaven.p2p', 
            'datahaven.forms',
            'datahaven.lib',
            'datahaven.lib.shtoom',            
            'datahaven.lib.transport',
            'datahaven.cspace',
            'datahaven.cspace.dht',
            'datahaven.cspace.main',
            'datahaven.cspace.network',
            'datahaven.cspace.util',
            'datahaven.nitro',
            'datahaven.ncrypt0',
            ],
)




