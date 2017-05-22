#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pkgversion import list_requirements, pep440_version, write_setup_py
from setuptools import find_packages

write_setup_py(
    name='bitdust',
    version=pep440_version(),
    description="BitDust Software",
    long_description=open('README.txt').read(),
    author="Veselin Penev",
    author_email='bitdust.io@gmail.com',
    url='ssh://git@gitlab.bitdust.io:devel/bitdust.devel.git',
    install_requires=list_requirements('requirements.txt'),
    packages=find_packages(),
    tests_require=['tox'],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ]
)
