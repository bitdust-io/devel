#!/usr/bin/python
# friends.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (friends.py) is part of BitDust Software.
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
"""
.. module:: friends

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 4

#------------------------------------------------------------------------------

import sys

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from bitdust.lib import strng

from bitdust.userid import global_id
from bitdust.userid import id_url

#------------------------------------------------------------------------------

# def do_add(idurl, result_defer, alias):
#     added = False
#     if not contactsdb.is_correspondent(idurl):
#         contactsdb.add_correspondent(idurl, alias)
#         contactsdb.save_correspondents()
#         added = True
#         events.send('friend-added', data=dict(
#             idurl=idurl,
#             global_id=global_id.idurl2glob(idurl),
#             alias=alias,
#         ))
#     d = online_status.handshake(idurl, channel='friend_add', keep_alive=True)
#     if share_person_key:
#         from bitdust.access import key_ring
#         from bitdust.crypt import my_keys
#         my_person_key_id = my_id.getGlobalID(key_alias='person')
#         if my_keys.is_key_registered(my_person_key_id):
#             d.addCallback(lambda *args: [
#                 key_ring.share_key(
#                     key_id=my_person_key_id,
#                     trusted_idurl=idurl,
#                     include_private=False,
#                     include_signature=True,
#                     timeout=15,
#                 ),
#                 result_defer.callback(),
#             ])
#
#     if _Debug:
#         d.addErrback(lg.errback, debug=_Debug, debug_level=_DebugLevel, method='api.friend_add')
#     d.addErrback(result_defer)
#     if added:
#         return OK(message='new friend has been added', api_method='friend_add')
#     return OK(message='this friend has been already added', api_method='friend_add')


def add_friend(trusted_user_id, alias='', share_person_key=True):
    idurl = strng.to_text(trusted_user_id)
    if global_id.IsValidGlobalUser(trusted_user_id):
        idurl = global_id.GlobalUserToIDURL(trusted_user_id, as_field=False)
    idurl = id_url.field(idurl)
    if not idurl:
        return None

    ret = Deferred()


#     if id_url.is_cached(idurl):
#         _add(idurl, ret)
#         return ret
#
#     d = identitycache.immediatelyCaching(idurl)
#     d.addErrback(lambda *args: ret.callback(ERROR('failed caching user identity')))
#     d.addCallback(lambda *args: _add(idurl, ret))
#     return ret
