import os
import time

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import Deferred  # @UnresolvedImport

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
        servers_list = ['127.0.0.1:15658']
    else:
        servers_list = ['{}:{}'.format(k, v) for k, v in known_bismuth_nodes.nodes_by_host().items()]
    _BismuthClient = bismuthclient.BismuthClient(
        servers_list=servers_list,
        wallet_file=wallet_file_path(),
        verbose=_Debug,
    )
    ret = Deferred()
    reactor.callLater(0, check_create_wallet, ret)  # @UndefinedVariable
    return ret


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


def check_create_wallet(result_defer):
    file_path = wallet_file_path()
    if _Debug:
        lg.args(_DebugLevel, file_path=file_path)
    if os.path.isfile(file_path):
        if _Debug:
            lg.dbg(_DebugLevel, 'wallet file already exists')
    else:
        if client().new_wallet(file_path):
            client().load_wallet(file_path)
        else:
            result_defer.errback(Exception('error creating wallet'))
            return

    success = None
    count = 0
    while True:
        if count > 10:
            success = False
            break
        try:
            cur_balance = client().balance()
        except Exception as e:
            lg.warn(e)
            time.sleep(5)
            count += 1
            continue
        if _Debug:
            lg.args(_DebugLevel, cur_balance=cur_balance, my_wallet_address=my_wallet_address())
        if cur_balance == 'N/A':
            time.sleep(5)
            count += 1
            continue
        success = True
        break

    if not success:
        result_defer.errback(Exception('error connecting to Bismuth node'))
        return
    result_defer.callback(True)


def my_wallet_address():
    return client().address


def my_balance():
    try:
        _balance = float(client().balance())
    except:
        lg.exc()
        return 'N/A'
    return _balance


def latest_transactions(num, offset, for_display, mempool_included):
    return client().latest_transactions(num, offset, for_display, mempool_included)


def send_transaction(recipient, amount, operation='', data='', raise_errors=False):
    error_reply = []
    ret = client().send(recipient=recipient, amount=amount, operation=operation, data=data, error_reply=error_reply)
    if not ret:
        if raise_errors:
            raise Exception(error_reply)
        return error_reply
    return ret


def find_transaction(address=None, recipient=None, operation=None, openfield=None, limit=10, offset=0):
    try:
        ret = client().search_transactions(
            address=address,
            recipient=recipient,
            operation=operation,
            openfield=openfield,
            limit=limit,
            offset=offset,
        )
    except:
        lg.exc()
        return []
    if _Debug:
        lg.args(_DebugLevel, a=address, r=recipient, o=operation, d=openfield, lim=limit, ofs=offset, ret=ret)
    return ret
