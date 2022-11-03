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

from bitdust.system import bpio
from bitdust.system import local_fs

from bitdust.lib import serialization

from bitdust.main import settings

#------------------------------------------------------------------------------


def find_network_config_file():
    networks_json_path = os.path.join(settings.MetaDataDir(), 'networkconfig')
    if not os.path.isfile(networks_json_path):
        # use hard-coded default_network.json file from the repository root
        networks_json_path = os.path.join(bpio.getExecutableDir(), 'default_network.json')
        if not os.path.isfile(networks_json_path):
            networks_json_path = os.path.join(bpio.getExecutableDir(), '..', 'default_network.json')
    return networks_json_path


def read_network_config_file():
    networks_json_path = find_network_config_file()
    if os.path.isfile(networks_json_path):
        network_info = serialization.BytesToDict(
            local_fs.ReadBinaryFile(networks_json_path),
            keys_to_text=True,
            values_to_text=True,
        )
        if network_info:
            return network_info
    from bitdust.main.default_network import default_network_info  # @UnresolvedImport
    return default_network_info()
