from distutils.core import setup

setup(  name='bitpie',
        version='{version}',
        author='Veselin Penev, BitPie.NET Inc.',
        author_email='veselin@bitpie.net',
        maintainer='Veselin Penev, BitPie.NET Inc.',
        maintainer_email='veselin@bitpie.net',
        url='http://bitpie.net',
        description='p2p communication tool',
        long_description='p2p communication tool',
        download_url='http://bitpie.net',
        license='Copyright BitPie.NET Inc., 2014',
        
        keywords='''p2p, peer to peer, peer, to, 
                    backup, restore, storage, data, recover,
                    distributed, online, 
                    python, twisted, 
                    encryption, crypto, protection,''',
        
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
            'Programming Language :: Python :: 2.7',
            'Topic :: Security',
            'Topic :: Security :: Cryptography',
            'Topic :: System :: Archiving :: Backup',
            'Topic :: System :: Distributed Computing',
            'Topic :: Utilities',
            ],

        packages=[
            'bitpie',
            'bitpie.crypt',
            'bitpie.dht',
            'bitpie.dht.entangled',
            'bitpie.dht.entangled.kademlia',
            'bitpie.forms',
            'bitpie.interface',
            'bitpie.lib',
            'bitpie.lib.shtoom',            
            'bitpie.logs',
            'bitpie.p2p',
            'bitpie.parallelp',
            'bitpie.parallelp.pp',
            'bitpie.raid',
            'bitpie.stun',
            'bitpie.tests',
            'bitpie.transport',
            'bitpie.transport.udp',
            'bitpie.userid',
            ],

        package_data = {
            'bitpie': [ 'automats/*', 'icons/*', 'fonts/*', 'parallelp/README', ],
            'bitpie.dht' : ['dht/entangled/*', ],
            'bitpie.parallelp': ['parallelp/pp/*', ],
            },

)




