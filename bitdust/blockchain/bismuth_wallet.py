import os

from bitdust_forks.Bismuth.bismuthclient import bismuthclient

_BismuthClient = None
_DataDirPath = None


def init(data_dir_path, servers_list, verbose=True):
    global _BismuthClient
    global _DataDirPath
    _DataDirPath = data_dir_path
    _BismuthClient = bismuthclient.BismuthClient(verbose=verbose, servers_list=servers_list)


def shutdown():
    global _BismuthClient
    global _DataDirPath
    del _BismuthClient
    _BismuthClient = None
    _DataDirPath = None


def client():
    global _BismuthClient
    return _BismuthClient


def data_dir():
    global _DataDirPath
    return _DataDirPath


def check_create_wallet():
    file_name = os.path.join(data_dir(), 'wallet.der')
    if os.path.isfile(file_name):
        print('Wallet file already exists')
    else:
        if client().new_wallet(file_name):
            client().load_wallet(file_name)
        else:
            print('Error creating wallet')


def latest_transactions(num, offset, for_display, mempool_included):
    return client().latest_transactions(num, offset, for_display, mempool_included)
