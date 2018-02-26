#!/usr/bin/python
#pybc_service.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (pybc_service.py) is part of BitDust Software.
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


"""
.. module:: pybc_service

I am running this locally from command line.
Started several instances on same local machine, configuration files are split and separated for every process/node.
Say you have local folders: _1, _2, _3 and _4 for each node respectively.
Then you can test it that way, run every command in a separate terminal window:

First node:

    python pybc_service.py --blockstore=_1/blocks --keystore=_1/keys --peerstore=_1/peers --port=8001 --loglevel=DEBUG --seeds="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004"


Second node, this will also run block explorer on port 9002:

    python pybc_service.py --block_explorer=9002 --blockstore=_2/blocks --keystore=_2/keys --peerstore=_2/peers --port=8002 --loglevel=DEBUG --seeds="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004"


Third node, this will also run a wallet UI on port 9003:

    python pybc_service.py --wallet=9003 --blockstore=_3/blocks --keystore=_3/keys --peerstore=_3/peers --port=8003 --loglevel=DEBUG --seeds="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004"


Fourth node, this will start a minining process, will wait for incoming transactions, will try to solve a block and write into blockchain:

    python pybc_service.py --mine --blockstore=_4/blocks --keystore=_4/keys --peerstore=_4/peers --port=8004 --loglevel=DEBUG --seeds="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004"


Fifth node, this will also start a minining process, but will only solve one block containing usefull info:

    python pybc_service.py --generate --json='{"this":"is",1:["cool", "!"]}' --blockstore=_5/blocks --keystore=_5/keys --peerstore=_5/peers --port=8005 --loglevel=DEBUG --seeds="127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004"


"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 4

#------------------------------------------------------------------------------

import os
import sys
import json
import logging
import time

from twisted.internet import reactor

#------------------------------------------------------------------------------

# This is a simple hack to be able to execute this module directly from command line for testing purposes
if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from main import events

#------------------------------------------------------------------------------

import pybc.util
import pybc.json_coin
import pybc.token

#------------------------------------------------------------------------------

_SeenAddresses = set()  # Keep a global set of addreses we have seen in blocks.
_PeerNode = None
_PeerListener = None
_BlockExplorerListener = None
_WalletListener = None
_Wallet = None
_BlockInProgress = None

#------------------------------------------------------------------------------

def init(host='127.0.0.1',
         port=8008,
         seed_nodes=[],
         blockstore_filename='./blockstore',
         keystore_filename='./keystore',
         peerstore_filename='./peerstore',
         minify=None,
         loglevel='INFO',
         logfilepath='/tmp/pybc.log',
         stats_filename=None,
         ):
    global _PeerNode
    global _Wallet
    if _Debug:
        lg.out(_DebugLevel, 'pybc_service.init')
    # Set the log level
    pybc.util.set_loglevel(loglevel, logformat="%(asctime)s [%(module)s] %(message)s", logfilename=logfilepath)
    if stats_filename is not None:
        # Start the science
        pybc.science.log_to(stats_filename)
    if not os.path.exists(os.path.dirname(blockstore_filename)):
        os.makedirs(os.path.dirname(blockstore_filename))
    if not os.path.exists(os.path.dirname(keystore_filename)):
        os.makedirs(os.path.dirname(keystore_filename))
    if not os.path.exists(os.path.dirname(peerstore_filename)):
        os.makedirs(os.path.dirname(peerstore_filename))
    logging.info("Starting server on {}:{}".format(host, port))
    pybc.science.log_event("startup")
    # Make a CoinBlockchain, using the specified blockchain file
    logging.info("Loading blockchain from {}".format(blockstore_filename))
    blockchain = pybc.token.TokenBlockchain(blockstore_filename, minification_time=minify)
    # Listen to it so we can see incoming new blocks going forward and read
    # their addresses.
    blockchain.subscribe(on_event)
    # Make a Wallet that uses the blockchain and our keystore
    logging.info("Loading wallet keystore from {}".format(keystore_filename))
    _Wallet = pybc.token.TokenWallet(blockchain, keystore_filename)
    logging.info("Wallet address: {}".format(pybc.util.bytes2string(_Wallet.get_address())))
    logging.info("Current balance: {}".format(_Wallet.get_balance()))
    # Now make a Peer.
    logging.info("Loading peers from {}".format(peerstore_filename))
    _PeerNode = pybc.Peer(
        "PyBC-Coin", 2, blockchain,
        peer_file=peerstore_filename,
        external_address=host,
        port=port,
    )

    def _on_listenere_started(l):
        global _PeerListener
        _PeerListener = l

    _PeerNode.listener.addCallback(_on_listenere_started)
    # Start connecting to seed nodes
    for peer_host, peer_port in seed_nodes:
        if peer_host == host and peer_port == port:
            # Skip our own node
            continue
        logging.info('Connecting via TCP to peer {}:{}'.format(peer_host, peer_port))
        _PeerNode.connect(peer_host, peer_port)
        _PeerNode.peer_seen(peer_host, peer_port, None)
    logging.info("Number of blocks: {}".format(len(_PeerNode.blockchain.blockstore)))
    logging.info("INIT DONE")


def shutdown():
    global _PeerListener
    global _PeerNode
    if _Debug:
        lg.out(_DebugLevel, 'pybc_service.shutdown')
    stop_block_explorer()
    stop_wallet()
    if _PeerListener:
        """ TODO: """
        _PeerListener.loseConnection()
        if _Debug:
            lg.out(_DebugLevel, '    peer listener stopped')
    else:
        if _Debug:
            lg.out(_DebugLevel, '    peer listener not initialized')
    _PeerListener = None
    _PeerNode = None

#------------------------------------------------------------------------------

def node():
    global _PeerNode
    return _PeerNode


def wallet():
    global _Wallet
    return _Wallet

#------------------------------------------------------------------------------

def seed_nodes():
    known_nodes = [
        #         ('208.78.96.185', 9100),    # datahaven.net
        #         ('67.207.147.183', 9100),   # identity.datahaven.net
        #         ('185.5.250.123', 9100),    # p2p-id.ru
        #         ('86.110.117.159', 9100),   # veselin-p2p.ru
        #         ('185.65.200.231', 9100),   # bitdust.io
        #         ('45.32.246.95', 9100),     # bitdust.ai

        ('datahaven.net', 9100),    # datahaven.net
        ('identity.datahaven.net', 9100),   # identity.datahaven.net
        ('p2p-id.ru', 9100),    # p2p-id.ru
        ('veselin-p2p.ru', 9100),   # veselin-p2p.ru
        ('bitdust.io', 9100),   # bitdust.io
        ('work.offshore.ai', 9100),     # bitdust.ai
    ]
    if _Debug:
        # add 5 local nodes for testing
        known_nodes.extend([
            ('127.0.0.1', 9100),
            ('127.0.0.1', 9100),
            ('127.0.0.1', 9100),
            ('127.0.0.1', 9100),
            ('127.0.0.1', 9100),
        ])
    return known_nodes

#------------------------------------------------------------------------------

def on_event(event, argument):
    """
    A function that listens to the blockchain and collects addresses from
    incoming blocks.
    """
    logging.info("EVENT: [{}] with {} bytes".format(event, len(str(argument))))
    events.send('blockchain-{}'.format(event), )  # data=dict(argument=argument))
#     global _SeenAddresses
#     if event == "forward":
#         # We're moving forward a block, and the argument is a block.
#         if argument.has_body:
#             # Only look at blocks that actually have transactions in them.
#             for transaction_bytes in pybc.transactions.unpack_transactions(argument.payload):
#                 # Turn each transaction into a Transaction object.
#                 transaction = pybc.json_coin.JsonTransaction.from_bytes(transaction_bytes)
#                 for _, _, _, source, json_data in transaction.inputs:
#                     # Nothe that we saw a transaction from this source
#                     _SeenAddresses.add(source)
#                     logging.info('{} >>>>>>>> {}'.format(
#                         pybc.util.bytes2string(source), json_data))
#                 for _, destination, json_data in transaction.outputs:
#                     # Note that we saw a transaction to this destination
#                     _SeenAddresses.add(destination)
#                     logging.info('{} <<<<<<<< {}'.format(
#                         pybc.util.bytes2string(destination), json_data))

#------------------------------------------------------------------------------

def start_block_explorer(port_number, peer_instance):
    """
    """
    global _BlockExplorerListener
    if _BlockExplorerListener:
        logging.info('Block Explorer already started')
        return False
    logging.info('Starting Block Explorer on port %d, peer network versions is: %s/%s' % (port_number, peer_instance.network, peer_instance.version))
    import pybc.block_explorer
    _BlockExplorerListener = pybc.block_explorer.start(port_number, peer_instance)
    return True


def stop_block_explorer():
    """
    """
    global _BlockExplorerListener
    if not _BlockExplorerListener:
        logging.info('Block Explorer not started')
        return False
    _BlockExplorerListener.loseConnection()
    logging.info("Block Explorer stopped")
    return True

#------------------------------------------------------------------------------

def start_wallet(port_number, peer_instance, wallet_instance):
    """ TODO: listener.loseConnection() """
    global _WalletListener
    if _WalletListener:
        logging.info('Wallet already started')
        return False
    logging.info('Starting Wallet on port %d, peer network versions is: %s/%s' % (port_number, peer_instance.network, peer_instance.version))
    import pybc.wallet
    _WalletListener = pybc.wallet.start(port_number, peer_instance, wallet_instance)
    return True


def stop_wallet():
    global _WalletListener
    if not _WalletListener:
        logging.info('Wallet not started')
        return False
    _WalletListener.loseConnection()
    logging.info("Wallet stopped")
    return True

#------------------------------------------------------------------------------

def generate_block(json_data=None, with_inputs=True, repeat=False, threaded=True):
    """
    Keep on generating blocks in the background.
    Put the blocks in the given peer's blockchain, and send the proceeds to the
    given wallet.
    Don't loop indefinitely, so that the Twisted main thread dying will stop
    us.
    """
    global _PeerNode
    global _Wallet
    global _BlockInProgress
    success = False

    if not _PeerNode:
        logging.info("Peer node is not exist, stop")
        return None

    if _BlockInProgress is None:
        if with_inputs and not _PeerNode.blockchain.transactions:
            logging.info("Blockchain is empty, skip block generation and wait for incoming transactions, retry after 10 seconds...")
            if repeat:
                reactor.callLater(10, generate_block, json_data, with_inputs, repeat,)
            return None
        # We need to start a new block
        _BlockInProgress = _PeerNode.blockchain.make_block(
            _Wallet.get_address(),
            json_data=json_data,  # timestamped_json_data,
            with_inputs=with_inputs,
        )
        if _BlockInProgress is not None:
            lg.info('started block generation with %d bytes json data, receiving address is %s, my ballance is %s' % (
                len(json.dumps(json_data)), pybc.util.bytes2string(_Wallet.get_address()), _Wallet.get_balance()))
            logging.info("Starting a block!")
            # Might as well dump balance here too
            logging.info("Receiving address: {}".format(pybc.util.bytes2string(_Wallet.get_address())))
            logging.info("Current balance: {}".format(_Wallet.get_balance()))
        else:
            if repeat:
                logging.info('Not able to start a new block, retry after 10 seconds...')
                reactor.callLater(10, generate_block, json_data, with_inputs, repeat, )
            else:
                logging.info('Failed to start a new block')
            return None

    else:
        # Keep working on the block we were working on
        success = _BlockInProgress.do_some_work(_PeerNode.blockchain.algorithm)
        if success:
            # We found a block!
            logging.info("Generated a block !!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # Dump the block
            logging.info("{}".format(_BlockInProgress))
            for transaction_bytes in pybc.unpack_transactions(_BlockInProgress.payload):
                logging.info("{}".format(pybc.json_coin.JsonTransaction.from_bytes(transaction_bytes)))
            _PeerNode.send_block(_BlockInProgress)
            # Start again
            _BlockInProgress = None
        else:
            if int(time.time()) > _BlockInProgress.timestamp + 60:
                # This block is too old. Try a new one.
                logging.info("Current generating block is {} seconds old. Restart mining!".format(
                    int(time.time()) - _BlockInProgress.timestamp))
                _BlockInProgress = None
            elif (_PeerNode.blockchain.highest_block is not None and
                  _PeerNode.blockchain.highest_block.block_hash() != _BlockInProgress.previous_hash):
                # This block is no longer based on the top of the chain
                logging.info("New block from elsewhere! Restart generation!")
                _BlockInProgress = None

    if threaded:
        # Tell the main thread to make us another thread.
        reactor.callFromThread(reactor.callInThread, generate_block,
                               json_data=json_data, with_inputs=with_inputs, repeat=repeat, threaded=threaded)
        return None

    if not _BlockInProgress:
        return success

    # now _BlockInProgress must exist and we will start mining directly in that thread
    return generate_block(json_data=json_data, with_inputs=with_inputs, repeat=repeat, threaded=threaded)

#------------------------------------------------------------------------------

def new_transaction(destination, amount, json_data, auth_data=None):
    global _Wallet
    global _PeerNode
    if amount <= 0:
        raise Exception('negative amount')
    # How much fee should we pay? TODO: make this dynamic or configurable
    fee = 1
    # How much do we need to send this transaction with its fee?
    total_input = amount + fee
    current_balance = _Wallet.get_balance()
    if total_input > current_balance:
        raise Exception("Insufficient funds! Current balance is {}, but {} needed".format(
            current_balance, total_input))
    # If we get here this is an actually sane transaction.
    # Make the transaction
    transaction = _Wallet.make_simple_transaction(
        amount,
        pybc.util.string2bytes(destination),
        fee=fee,
        json_data=json_data,
        auth_data=auth_data,
    )
    # The user wants to make the transaction. Send it.
    if not transaction:
        logging.warning('Failed to create a new transaction: {} to {}'.format(amount, destination))
    else:
        logging.info('Starting a new transaction:\n{}'.format(str(transaction)))
        _PeerNode.send_transaction(transaction.to_bytes())
    return transaction

#------------------------------------------------------------------------------

def _default_location(filename):
    return os.path.join(os.path.expanduser('~'), '.pybc', filename)


def _parse_args(args):
    import argparse
    args = args[1:]
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--blockstore", default=_default_location('blocks'),
                        help="the name of a file to store blocks in")
    parser.add_argument("--keystore", default=_default_location('keys'),
                        help="the name of a file to store keys in")
    parser.add_argument("--peerstore", default=_default_location('peers'),
                        help="the name of a file to store peer addresses in")
    parser.add_argument("--host", default='127.0.0.1',
                        help="the host or IP to advertise to other nodes")
    parser.add_argument("--port", type=int, default=58585,
                        help="the port to listen on")
    parser.add_argument("--seeds", default='127.0.0.1:58501,127.0.0.1:58502,127.0.0.1:58503,127.0.0.1:58504',
                        help="default set of seed nodes")
    parser.add_argument("--minify", type=int, default=None,
                        help="minify blocks burried deeper than this")
    parser.add_argument("--transaction", action="store_true",
                        help="create a new transaction")
    parser.add_argument("--destination",
                        help="destination address for new transaction")
    parser.add_argument("--amount", type=int,
                        help="amount of coins for new transaction")
    parser.add_argument("--json", default='{}',
                        help="json data to store in the new transaction")
    parser.add_argument("--generate", action="store_true",
                        help="generate a block with inputs every so often")
    parser.add_argument("--mine", action="store_true",
                        help="generate any blocks, just to get some rewards and mine coins")
    parser.add_argument("--wallet", type=int, default=None,
                        help="start wallet http listener, set port to listen on")
    parser.add_argument("--block_explorer", type=int, default=None,
                        help="start block explorer http listener, set port to listen on")
    parser.add_argument("--stats",
                        help="filename to log statistics to, for doing science")
    parser.add_argument("--loglevel", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", ],
                        help="logging level to use")
    parser.add_argument("--pdbshell", action="store_true",
                        help="import and run pdb set_trace() shell")
    return parser.parse_args(args)

#------------------------------------------------------------------------------

def main():
    global _PeerNode
    global _Wallet
    lg.set_debug_level(16)
    lg.life_begins()
    options = _parse_args(sys.argv)
    init(
        host=options.host,
        port=options.port,
        seed_nodes=[(i.split(':')[0], int(i.split(':')[1]), ) for i in options.seeds.split(',')],
        blockstore_filename=options.blockstore,
        keystore_filename=options.keystore,
        peerstore_filename=options.peerstore,
        loglevel='DEBUG' if _Debug else 'INFO',
    )
    if options.block_explorer:
        reactor.callLater(1, start_block_explorer,
                          options.block_explorer, _PeerNode)
    if options.wallet:
        reactor.callLater(1, start_wallet,
                          options.wallet, _PeerNode, _Wallet)
    if options.generate:
        reactor.callFromThread(generate_block,
                               json_data=dict(started=time.time(), data=json.loads(options.json)),
                               with_inputs=False,
                               repeat=False, )
    if options.mine:
        reactor.callFromThread(generate_block,
                               json_data=dict(started=time.time(), data=json.loads(options.json)),
                               with_inputs=True,
                               repeat=True, )
    if options.transaction:
        reactor.callLater(5, new_transaction,
                          options.destination,
                          options.amount,
                          json.loads(options.json), )
    if options.pdbshell:
        import pdb
        pdb.set_trace()
        return

    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
    reactor.callLater(5, shutdown)
    reactor.run()


if __name__ == "__main__":
    main()
