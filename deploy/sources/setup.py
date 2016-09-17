#!/usr/bin/env python
#setup.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (setup.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
from distutils.core import setup

setup(  name='bitdust',
        version='{version}',
        author='Veselin Penev, BitDust Inc.',
        author_email='bitdust.io@gmail.com',
        maintainer='Veselin Penev, BitDust Inc.',
        maintainer_email='veselin@bitdust.io',
        url='http://bitdust.io',
        description='p2p communication tool',
        long_description='p2p communication tool',
        download_url='http://bitdust.io',
        license='Copyright BitDust Inc., 2014',
        
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
            'bitdust',
            'bitdust.automats',
            'bitdust.chat',
            'bitdust.contacts',
            'bitdust.crypt',
            'bitdust.currency',
            'bitdust.customer',
            'bitdust.dht',
            'bitdust.dht.entangled',
            'bitdust.dht.entangled.kademlia',
            'bitdust.forms',
            'bitdust.interface',
            'bitdust.lib',
            'bitdust.lib.fastjsonrpc',
            'bitdust.logs',
            'bitdust.main',
            'bitdust.p2p',
            'bitdust.parallelp',
            'bitdust.parallelp.pp',
            'bitdust.raid',
            'bitdust.services',
            'bitdust.storage',
            'bitdust.stun',
            'bitdust.stun.shtoom',
            'bitdust.supplier',
            'bitdust.system',
            'bitdust.transport',
            'bitdust.transport.udp',
            'bitdust.transport.tcp',
            'bitdust.updates',
            'bitdust.userid',
            'bitdust.web',
            'bitdust.web.asite',
            'bitdust.web.customerapp',
            'bitdust.web.friendapp',
            'bitdust.web.identityapp',
            'bitdust.web.jqchatapp',
            'bitdust.web.myfilesapp',
            'bitdust.web.setupapp',
            'bitdust.web.supplierapp',
            ],

        package_data = {
            'bitdust': [ 
                        'parallelp/README', 
                        'dht/entangled/AUTHORS', 
                        'dht/entangled/COPYING', 
                        'dht/entangled/README', 
                        'parallelp/pp/*', 
                        'deploy/windows/*.bat',
                        'icons/*',
                        'fonts/*',
                        'lib/fastjsonrpc/LICENSE',
                        'userid/id_server_apache2_conf',
                        'userid/run.id_server',
                        'userid/apache2_config.sh',
                        '*.txt',
                      ],
            },

)




