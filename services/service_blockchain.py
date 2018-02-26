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

    # flag_public_key_registered = False
    # flag_public_key_transaction_sent = False

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
        from twisted.internet import reactor
        from main import config
        from main import settings
        from main import events
        from blockchain import pybc_service
        self.flag_public_key_registered = False
        self.flag_public_key_transaction_sent = False
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
            logfilepath=os.path.join(pybc_home, 'log'),
            stats_filename=None,
        )
        if config.conf().getBool('services/blockchain/explorer/enabled'):
            pybc_service.start_block_explorer(config.conf().getInt('services/blockchain/explorer/port'), pybc_service.node())
        if config.conf().getBool('services/blockchain/wallet/enabled'):
            pybc_service.start_wallet(config.conf().getInt('services/blockchain/wallet/port'), pybc_service.node(), pybc_service.wallet())
        if config.conf().getBool('services/blockchain/miner/enabled'):
            reactor.callFromThread(pybc_service.generate_block,
                                   json_data={},
                                   with_inputs=True,
                                   repeat=True, )
        events.add_subscriber(self._on_local_identity_modified, 'local-identity-modified')
        events.add_subscriber(self._on_blockchain_forward, 'blockchain-forward')
        events.add_subscriber(self._on_blockchain_sync, 'blockchain-sync')
        reactor.callLater(0, self._do_check_register_my_identity)
        return True

    def stop(self):
        from blockchain import pybc_service
        pybc_service.shutdown()
        self.flag_public_key_registered = False
        self.flag_public_key_transaction_sent = False
        return True

    def _on_blockchain_forward(self, evt):
        self._do_check_register_my_identity()
        return True

    def _on_blockchain_sync(self, evt):
        self._do_check_register_my_identity()
        return True

    def _on_local_identity_modified(self, evt):
        self._do_check_register_my_identity()
        return True

    def _do_check_register_my_identity(self):
        if self.flag_public_key_registered:
            return True
        from logs import lg
        from userid import my_id
        from blockchain import pybc_service
        from blockchain.pybc import util
        if not pybc_service.node().blockchain.state_available:
            lg.warn('skip, blockchain is not ready yet')
            return False
        found = False
        for tr in pybc_service.node().blockchain.iterate_transactions_by_address(pybc_service.wallet().get_address()):
            if found:
                break
            for auth in tr.authorizations:
                try:
                    auth_data = util.bytes2string(auth[2])
                except:
                    continue
                if not auth_data or 'k' not in auth_data:
                    continue
                if auth_data['k'] == my_id.getLocalIdentity().publickey:
                    found = True
                    break
        if found:
            self.flag_public_key_registered = True
            lg.info('found my public key in the blockchain')
            return True
        if pybc_service.wallet().get_balance() < 2:
            lg.info('my balance is %d, need to mine a block to be able to register' % pybc_service.wallet().get_balance())
            self._do_solve_block(json_data={'a': 'pay', 'u': my_id.getLocalIdentity().getIDName(), })
        if pybc_service.wallet().get_balance() < 2:
            lg.warn('not able to mine some coins')
            return False
        if not self.flag_public_key_transaction_sent:
            lg.info('my balance is %d, starting new transaction to store my public key in the blockchain' % pybc_service.wallet().get_balance())
            tr = pybc_service.new_transaction(
                destination=util.bytes2string(pybc_service.wallet().get_address()),
                amount=1,
                json_data={'a': 'register', 'u': my_id.getLocalIdentity().getIDName(), },
                auth_data={
                    'k': my_id.getLocalIdentity().publickey,
                    'u': my_id.getLocalIdentity().getIDName(),
                    'd': my_id.getLocalIdentity().date,
                },
            )
            if tr:
                self.flag_public_key_transaction_sent = True
        return False

    def _do_solve_block(self, json_data=None):
        from blockchain import pybc_service
        new_block = pybc_service.node().blockchain.make_block(
            pybc_service.wallet().get_address(),
            json_data=json_data,
            with_inputs=False,
        )
        if not new_block:
            return None
        if not new_block.do_some_work(pybc_service.node().blockchain.algorithm, iterations=10000000):
            return None
        pybc_service.node().send_block(new_block)
        return new_block
