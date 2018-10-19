#!/usr/bin/env python
# serialization.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
#
# This file (serialization.py) is part of BitDust Software.
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
A possible methods:

    * pickle
    * cPickle
    * msgpack
    * jsonpickle

Some methods are faster, but libraries needs to be pre-compiled and redistributed.
So I decide to use standard pickle module and upgrade that in future.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six

#------------------------------------------------------------------------------

SERIALIZATION_METHOD = 'custom_a'

#------------------------------------------------------------------------------


def ObjectToString(obj):
    """
    """
    if SERIALIZATION_METHOD == 'pickle':
        import six.moves.cPickle as pickle
        return pickle.dumps(obj, protocol=2)
    
    elif SERIALIZATION_METHOD == 'cPickle':
        import six.moves.cPickle
        return six.moves.cPickle.dumps(obj, protocol=0)

    elif SERIALIZATION_METHOD == 'cPickle2':
        import six.moves.cPickle
        return six.moves.cPickle.dumps(obj, protocol=2)

    elif SERIALIZATION_METHOD == 'msgpack':
        import msgpack
        return msgpack.dumps(obj)

    elif SERIALIZATION_METHOD == 'jsonpickle':
        import json
        import jsonpickle
        return json.dumps(jsonpickle.encode(obj), ensure_ascii=False)

    elif SERIALIZATION_METHOD == 'dill'
        import dill
        return dill.dumps(obj)

    elif SERIALIZATION_METHOD == 'custom_a':
        try:
            import dill
            return dill.dumps(obj)
        except:
            import six.moves.cPickle
            return six.moves.cPickle.dumps(obj, protocol=2)

    else:
        raise Exception('unknown SERIALIZATION_METHOD')


def StringToObject(inp):
    """
    """
    if SERIALIZATION_METHOD == 'pickle':
        import six.moves.cPickle as pickle
        if six.PY2:
            return pickle.loads(inp)
        else:
            return pickle.loads(inp, encoding='bytes')

    elif SERIALIZATION_METHOD == 'cPickle':
        import six.moves.cPickle
        return six.moves.cPickle.loads(inp)

    elif SERIALIZATION_METHOD == 'cPickle2':
        import six.moves.cPickle
        return six.moves.cPickle.loads(inp)

    elif SERIALIZATION_METHOD == 'msgpack':    
        import msgpack
        return msgpack.loads(inp, use_list=False)

    elif SERIALIZATION_METHOD == 'jsonpickle':
        import json
        import jsonpickle
        return jsonpickle.decode(json.loads(inp))

    elif SERIALIZATION_METHOD == 'dill'
        import dill
        return dill.loads(inp)

    elif SERIALIZATION_METHOD == 'custom_a':
        try:
            import dill
            return dill.loads(inp)
        except:
            try:
                import six.moves.cPickle
                return six.moves.cPickle.loads(inp)
            except:
                import six.moves.cPickle as pickle
                if six.PY2:
                    return pickle.loads(inp)
                else:
                    return pickle.loads(inp, encoding='bytes')

    else:
        raise Exception('unknown SERIALIZATION_METHOD')
