#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pkgversion import list_requirements, pep440_version, write_setup_py
from setuptools import find_packages

write_setup_py(
    name='bitdust',
    version='0.0.1',
    description="BitDust is a decentralized on-line storage network for safe, independent and private communications.",
    long_description=open('README.md').read(),
    author="Veselin Penev",
    author_email='bitdust.io@gmail.com',
    url='https://github.com/bitdust-io/public.git',
    install_requires=list_requirements('requirements.txt'),
    packages=find_packages(exclude=['tests*', 'deploy*', 'icons*', 'release*', 'scripts*', 'web*', ]),
    tests_require=[],
    include_package_data=True,
    zip_safe=False,
    license='GNU Affero General Public License v3 or later (AGPLv3+)',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Twisted',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
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
    ]
)
