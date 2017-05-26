#!/usr/bin/python
# coins_index.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (coins_index.py) is part of BitDust Software.
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

module:: coins_index
"""

#------------------------------------------------------------------------------

_Debug = True

#------------------------------------------------------------------------------

from hashlib import md5

from CodernityDB.hash_index import HashIndex
from CodernityDB.tree_index import TreeBasedIndex

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------

def definitions():
    return {
        'creator': Creator,
        'signer': Signer,
        'miner': Miner,
        'hash': HashID,
        'prev': PrevHashID,
        'supplier_customer': SupplierCustomer,
        'time_created': TimeCreated,
        'time_signed': TimeSigned,
        'time_mined': TimeMined,
    }

#------------------------------------------------------------------------------

class AbstractHashIndexByRole(HashIndex):
    role = None
    field = None
    key_format = '16s'

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = self.key_format
        super(AbstractHashIndexByRole, self).__init__(*args, **kwargs)

    def transform_key(self, key):
        return key

    def make_key_value(self, data):
        try:
            return self.transform_key(data[self.role][self.field]), None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return self.transform_key(key)

#------------------------------------------------------------------------------

class AbstractMD5IndexByRole(AbstractHashIndexByRole):

    def transform_key(self, key):
        return md5(key).digest()

#------------------------------------------------------------------------------

class AbstractMD5IndexByChain(HashIndex):
    producer_role = None
    consumer_role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = '16s'
        super(AbstractMD5IndexByChain, self).__init__(*args, **kwargs)

    def make_key_value(self, data):
        try:
            chain_id = '%s_%s' % (
                data['payload'][self.producer_role],
                data['payload'][self.consumer_role],
            )
            return md5(chain_id).digest(), None
        except (AttributeError, ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

    def make_key(self, key):
        return md5(key).digest()

#------------------------------------------------------------------------------

class AbstractTimeIndex(TreeBasedIndex):
    role = None

    def __init__(self, *args, **kwargs):
        kwargs['key_format'] = 'I'
        kwargs['node_capacity'] = 128
        super(AbstractTimeIndex, self).__init__(*args, **kwargs)

    def make_key(self, key):
        return key

    def make_key_value(self, data):
        try:
            return data[self.role]['time'], None
        except (ValueError, KeyError, IndexError, ):
            return None
        except Exception:
            lg.exc()

#------------------------------------------------------------------------------

class Creator(AbstractMD5IndexByRole):
    role = 'creator'
    field = 'idurl'

#------------------------------------------------------------------------------

class Signer(AbstractMD5IndexByRole):
    role = 'signer'
    field = 'idurl'

#------------------------------------------------------------------------------

class Miner(AbstractMD5IndexByRole):
    role = 'miner'
    field = 'idurl'

#------------------------------------------------------------------------------

class HashID(AbstractHashIndexByRole):
    role = 'miner'
    field = 'hash'
    key_format = '40s'

#------------------------------------------------------------------------------

class PrevHashID(AbstractHashIndexByRole):
    role = 'miner'
    field = 'prev'
    key_format = '40s'

#------------------------------------------------------------------------------

class SupplierCustomer(AbstractMD5IndexByChain):
    producer_role = 'supplier'
    consumer_role = 'customer'

#------------------------------------------------------------------------------

class TimeCreated(AbstractTimeIndex):
    role = 'creator'

#------------------------------------------------------------------------------

class TimeSigned(AbstractTimeIndex):
    role = 'signer'

#------------------------------------------------------------------------------

class TimeMined(AbstractTimeIndex):
    role = 'miner'
