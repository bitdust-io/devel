#!/usr/bin/env python
# setup.py
#
# Copyright (C) 2008 Veselin Penev, http://bitdust.io
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
from __future__ import absolute_import
from setuptools import setup

setup(
    name='bitdust',
    version='{version}',
    author='Veselin Penev, BitDust',
    author_email='bitdust.io@gmail.com',
    maintainer='Veselin Penev, BitDust',
    maintainer_email='veselin@bitdust.io',
    url='https://bitdust.io',
    description='p2p secure distributed storage and communication engine',
    long_description='p2p secure distributed storage and communication engine',
    download_url='https://bitdust.io',
    license='Copyright (C) 2008 Veselin Penev, https://bitdust.io',
    keywords='''p2p, peer to peer, backup, restore, storage, data, recover,
                distributed, online, python, twisted, messaging, websocket,
                encryption, crypto, protection''',
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
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Security',
        'Topic :: Security :: Cryptography',
        'Topic :: System :: Archiving :: Backup',
        'Topic :: System :: Distributed Computing',
        'Topic :: Utilities',
    ],
    packages=[
        'bitdust',
        'bitdust_forks',
    ],
    package_data={
        'bitdust_forks': [
            'bitdust_forks/entangled/AUTHORS',
            'bitdust_forks/entangled/COPYING',
            'bitdust_forks/entangled/README',
            'bitdust_forks/parallelp/README',
            'bitdust_forks/parallelp/pp/AUTHORS',
            'bitdust_forks/parallelp/pp/CHANGELOG',
            'bitdust_forks/parallelp/pp/COPYING',
            'bitdust_forks/parallelp/pp/PKG-INFO',
            'bitdust_forks/parallelp/pp/README',
            'bitdust_forks/txrestapi/LICENSE',
            'bitdust_forks/txrestapi/README.rst',
            'bitdust_forks/websocket/LICENSE',
            'bitdust_forks/CodernityDB/README',
            '*.txt',
            '*.md',
        ],
    },
    install_requires=[
        'Twisted==22.10.0',
        'zope.interface',
        'cryptography',
        'pycryptodomex',
        'service_identity',
        'pyparsing',
        'appdirs',
        'psutil',
        'cffi',
        'six',
        'virtualenv',
    ],
    scripts=[
        'scripts/bitdust',
        'scripts/bitdust_worker',
    ],
)
