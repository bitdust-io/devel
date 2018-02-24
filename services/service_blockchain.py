#!/usr/bin/python
# service_blockchain.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (service_blockchain.py) is part of BitDust Software.
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

module:: service_blockchain
"""

from services.local_service import LocalService


def create_service():
    return BlockchainService()


class BlockchainService(LocalService):

    service_name = 'service_blockchain'
    config_path = 'services/blockchain/enabled'

    def dependent_on(self):
        return ['service_tcp_connections',
                ]

    def installed(self):
        try:
            import os
            import sys
            dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
            blockchain_dir = os.path.abspath(os.path.join(dirpath, 'blockchain'))
            if blockchain_dir not in sys.path:
                sys.path.insert(0, blockchain_dir)
            from blockchain import pybc_service
        except:
            return False
        return True

    def start(self):
        import os
        from logs import lg
        from main import config
        from main import settings
        from blockchain import pybc_service
        pybc_home = settings.BlockchainDir()
        seeds = config.conf().getString('services/blockchain/seeds')
        if seeds:
            seed_nodes = [(i.split(':')[0], int(i.split(':')[1]), ) for i in seeds.split(',')]
        else:
            seed_nodes = pybc_service.seed_nodes()
        pybc_service.init(
            host=config.conf().getData('services/blockchain/host'),
            port=config.conf().getInt('services/blockchain/port'),
            seed_nodes=seed_nodes,
            blockstore_filename=os.path.join(pybc_home, 'blocks'),
            keystore_filename=os.path.join(pybc_home, 'keys'),
            peerstore_filename=os.path.join(pybc_home, 'peers'),
            minify=None,
            loglevel='DEBUG',
            stats_filename=None,  # os.path.join(pybc_home, 'log'),
        )
        if config.conf().getBool('services/blockchain/explorer/enabled'):
            pybc_service.start_block_explorer(config.conf().getInt('services/blockchain/explorer/port'), pybc_service.node())
        if config.conf().getBool('services/blockchain/wallet/enabled'):
            pybc_service.start_wallet(config.conf().getInt('services/blockchain/wallet/port'), pybc_service.node(), pybc_service.wallet())
        if config.conf().getBool('services/blockchain/miner/enabled'):
            from twisted.internet import reactor
            reactor.callFromThread(pybc_service.generate_block,
                                   json_data={},
                                   with_inputs=True,
                                   # with_outputs=True,
                                   repeat=True, )
        return True

    def stop(self):
        from blockchain import pybc_service
        pybc_service.shutdown()
        return True
