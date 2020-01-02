#!/usr/bin/python
# network_config.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (network_config.py) is part of BitDust Software.
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
#
#
#
#

"""
..

module:: network_config
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

import os

#------------------------------------------------------------------------------

from system import bpio
from system import local_fs
from lib import serialization
from main import settings

#------------------------------------------------------------------------------

def detect_network_name():
    my_network = local_fs.ReadTextFile(settings.NetworkFileName()).strip()
    if not my_network:
        my_network = 'main'
    return my_network


def find_network_config_file():
    networks_json_path = os.path.join(settings.MetaDataDir(), 'networkconfig')
    if not os.path.isfile(networks_json_path):
        # use hard-coded networks.json file from the repository root
        networks_json_path = os.path.join(bpio.getExecutableDir(), 'networks.json')
    return networks_json_path


def read_network_config_file():
    networks_json_path = find_network_config_file()
    networks_json = serialization.BytesToDict(
        local_fs.ReadBinaryFile(networks_json_path),
        keys_to_text=True,
        values_to_text=True,
    )
    my_network = detect_network_name()
    if my_network not in networks_json:
        my_network = 'main'
    network_info = networks_json[my_network]
    return network_info
