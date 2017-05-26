# supplier_customer
# SupplierCustomer

# inserted automatically
import os
import marshal

import struct
import shutil

from hashlib import md5

# custom db code start
# db_custom


# custom index code start
# ind_custom

from CodernityDB.hash_index import HashIndex
from CodernityDB.tree_index import TreeBasedIndex
from coins.coins_index import AbstractHashIndexByRole
from coins.coins_index import AbstractMD5IndexByRole
from coins.coins_index import AbstractMD5IndexByChain
from coins.coins_index import AbstractTimeIndex
from coins.coins_index import make_customer_header



# source of classes in index.classes_code
# classes_code


# index code start

class SupplierCustomer(AbstractMD5IndexByChain):
    custom_header = make_customer_header()
    producer_role = 'supplier'
    consumer_role = 'customer'
