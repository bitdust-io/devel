import os

#------------------------------------------------------------------------------

from bitdust_forks.Bismuth.bismuthclient import bismuthclient  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.main import settings

from bitdust.blockchain import known_bismuth_nodes

from bitdust.services import driver

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

_BismuthClient = None
_DataDirPath = None

#------------------------------------------------------------------------------


def init():
    global _BismuthClient
    global _DataDirPath
    _DataDirPath = settings.ServiceDir('bismuth_blockchain')
    if driver.is_enabled('service_bismuth_node'):
        servers_list = [
            '127.0.0.1:15658',
        ]
    else:
        servers_list = ['{}:{}'.format(k, v) for k, v in known_bismuth_nodes.nodes_by_host().items()]
    _BismuthClient = bismuthclient.BismuthClient(
        servers_list=servers_list,
        wallet_file=wallet_file_path(),
        verbose=_Debug,
    )
    check_create_wallet()


def shutdown():
    global _BismuthClient
    global _DataDirPath
    del _BismuthClient
    _BismuthClient = None
    _DataDirPath = None


#------------------------------------------------------------------------------


def client():
    global _BismuthClient
    return _BismuthClient


def data_dir():
    global _DataDirPath
    return _DataDirPath


def wallet_file_path(wallet_name=None):
    if not wallet_name:
        wallet_name = 'wallet'
    return os.path.join(data_dir(), wallet_name + '_key.json')


def check_create_wallet():
    file_path = wallet_file_path()
    if os.path.isfile(file_path):
        if _Debug:
            lg.dbg(_DebugLevel, 'wallet file already exists')
    else:
        if client().new_wallet(file_path):
            client().load_wallet(file_path)
        else:
            print('Error creating wallet')


def my_wallet_address():
    return client().address


def my_balance():
    return client().balance()


def latest_transactions(num, offset, for_display, mempool_included):
    return client().latest_transactions(num, offset, for_display, mempool_included)
