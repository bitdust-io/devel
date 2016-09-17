#!/usr/bin/python
#service_miner.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (service_miner.py) is part of BitDust Software.
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
.. module:: service_miner

"""

from services.local_service import LocalService

def create_service():
    return MinerService()
    
class MinerService(LocalService):
    
    service_name = 'service_miner'
    config_path = 'services/miner/enabled'
    
    def dependent_on(self):
        return ['service_p2p_hookups',
                'service_nodes_lookup',
                ]
    
    def start(self):
        from coins import coins_miner
        coins_miner.A('init')
        coins_miner.A('start')
        return True
    
    def stop(self):
        from coins import coins_miner
        coins_miner.A('stop')
        coins_miner.Destroy()
        return True
