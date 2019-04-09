#!/usr/bin/python
# api_rest_http_server.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (api_rest_http_server.py) is part of BitDust Software.
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

module:: api_rest_http_server
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 6

#------------------------------------------------------------------------------

import os

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.web.server import Site

#------------------------------------------------------------------------------

from logs import lg

from interface import api

from lib import strng
from lib import jsn
from lib import serialization

from lib.txrestapi.txrestapi.json_resource import JsonAPIResource
from lib.txrestapi.txrestapi.methods import GET, POST, PUT, DELETE, ALL

#------------------------------------------------------------------------------

_APIListener = None

#------------------------------------------------------------------------------

def init(port=None):
    global _APIListener
    if _APIListener is not None:
        lg.warn('_APIListener already initialized')
        return
    if not port:
        port = 8180
    try:
        api_resource = BitDustRESTHTTPServer()
        site = BitDustAPISite(api_resource, timeout=None)
        _APIListener = reactor.listenTCP(port, site)  # @UndefinedVariable
    except:
        lg.exc()
    lg.out(4, 'api_rest_http_server.init')


def shutdown():
    global _APIListener
    if _APIListener is None:
        lg.warn('_APIListener is None')
        return
    lg.out(4, 'api_rest_http_server.shutdown calling _APIListener.stopListening()')
    _APIListener.stopListening()
    del _APIListener
    _APIListener = None
    lg.out(4, '    _APIListener destroyed')

#------------------------------------------------------------------------------

def _request_arg(request, key, default='', mandatory=False):
    """
    Simplify extracting arguments from url query in request.
    """
    args = request.args or {}
    if key in args:
        values = args.get(key, [default, ])
        return strng.to_text(values[0]) if values else default
    if strng.to_bin(key) in args:
        values = args.get(strng.to_bin(key), [default, ])
        return strng.to_text(values[0]) if values else default
    if mandatory:
        raise Exception('mandatory url query argument missed: %s' % key)
    return default


def _request_data(request, mandatory_keys=[], default_value={}):
    """
    Simplify extracting input parameters from request body.
    """
    input_request_data = request.content.getvalue()
    if not input_request_data:
        if mandatory_keys:
            raise Exception('mandatory json input missed: %s' % mandatory_keys)
        return default_value
    try:
        data = serialization.BytesToDict(
            input_request_data,
            encoding='utf-8',
            keys_to_text=True,
            values_to_text=True,
        )
    except:
        raise Exception('invalid json input')
    for k in mandatory_keys:
        if isinstance(k, tuple):
            found = False
            for f in k:
                if f in data:
                    found = True
            if not found:
                raise Exception('one of mandatory parameters missed: %s' % k)
        else:
            if k not in data:
                raise Exception('one of mandatory parameters missed: %s' % mandatory_keys)
    return data

#------------------------------------------------------------------------------

class BitDustAPISite(Site):

    def buildProtocol(self, addr):
        """
        Only accepting connections from local machine!
        """
        if addr.host == '127.0.0.1':
            return Site.buildProtocol(self, addr)
        if not _Debug:
            return None
        if os.environ.get('BITDUST_API_PASS_EXTERNAL_CONNECTIONS', '0') != '1':
            return None
        return Site.buildProtocol(self, addr)


class BitDustRESTHTTPServer(JsonAPIResource):
    """
    A set of API method to interract and control locally running BitDust process.
    """

    #------------------------------------------------------------------------------

    def log_request(self, request, callback, args):
        if _Debug:
            _args = jsn.dict_items_to_text(request.args)
            if not _args:
                _args = _request_data(request)
            else:
                _args = {k : (v[0] if (v and isinstance(v, list)) else v) for k, v in _args.items()}
            try:
                func_name = callback.im_func.func_name
            except:
                func_name = callback.__name__
            if _Debug:
                uri = request.uri.decode()
                if uri not in [
                    '/event/listen/electron/v1',
                    '/network/connected/v1',
                    '/process/health/v1',
                ] or _DebugLevel > 10: 
                    lg.out(_DebugLevel, '*** %s:%s   will execute   api.%s(%r)' % (
                        request.method.decode(), uri, func_name, _args))
        return None

    #------------------------------------------------------------------------------

    @GET('^/p/st$')
    @GET('^/process/stop/v1$')
    def process_stop_v1(self, request):
        return api.process_stop()

    @GET('^/p/rst$')
    @GET('^/process/restart/v1$')
    def process_restart_v1(self, request):
        return api.process_restart(showgui=bool(request.args.get('showgui')))

    @GET('^/p/s$')
    @GET('^/process/show/v1$')
    def process_show_v1(self, request):
        return api.process_show()
    
    @GET('^/process/health/v1$')
    def process_health_v1(self, request):
        return api.process_health()

    @GET('^/process/debug/v1$')
    def process_shell_v1(self, request):
        return api.process_debug()

    #------------------------------------------------------------------------------

    @GET('^/c/l$')
    @GET('^/config/v1$')
    @GET('^/config/list/v1$')
    def config_list_v1(self, request):
        return api.config_list(sort=True)

    @GET('^/c/t$')
    @GET('^/config/tree/v1$')
    def config_tree_v1(self, request):
        return api.config_tree()

    @GET('^/c/g/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/$')
    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_get_l3_v1(self, request, key1, key2, key3):
        return api.config_get(key=(key1 + '/' + key2 + '/' + key3))

    @GET('^/c/g/(?P<key1>[^/]+)/(?P<key2>[^/]+)/$')
    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_get_l2_v1(self, request, key1, key2):
        return api.config_get(key=(key1 + '/' + key2))

    @GET('^/c/g/(?P<key>[^/]+)/$')
    @GET('^/config/get/(?P<key>[^/]+)/v1$')
    def config_get_l1_v1(self, request, key):
        return api.config_get(key=key)

    @GET('^/c/g$')
    @GET('^/config/get/v1$')
    def config_get_v1(self, request):
        # cgi.escape(dict({} or request.args).get('key', [''])[0]),)
        return api.config_get(key=_request_arg(request, 'key', mandatory=True))

    @POST('^/c/s/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/$')
    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_set_l3_v1(self, request, key1, key2, key3):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=(key1 + '/' + key2 + '/' + key3), value=data['value'])

    @POST('^/c/s/(?P<key1>[^/]+)/(?P<key2>[^/]+)/$')
    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_set_l2_v1(self, request, key1, key2):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=(key1 + '/' + key2), value=data['value'])

    @POST('^/c/s/(?P<key>[^/]+)/$')
    @POST('^/config/set/(?P<key>[^/]+)/v1$')
    def config_set_l1_v1(self, request, key):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=key, value=data['value'])

    @POST('^/c/s$')
    @POST('^/config/set/v1$')
    def config_set_v1(self, request):
        data = _request_data(request, mandatory_keys=['key', 'value', ])
        return api.config_set(key=data['key'], value=data['value'])

    #------------------------------------------------------------------------------

    @GET('^/i/l$')
    @GET('^/identity/list/v1$')
    def identity_list_v1(self, request):
        return api.identity_list()

    @GET('^/i/g$')
    @GET('^/identity/get/v1$')
    @GET('^/identity/my/v1$')
    @GET('^/identity/my/get/v1$')
    def identity_get_v1(self, request):
        return api.identity_get(
            include_xml_source=bool(_request_arg(request, 'include_xml_source', '0') in ['1', 'true', ]),
        )

    @POST('^/i/c$')
    @POST('^/identity/create/v1$')
    @POST('^/identity/my/create/v1$')
    def identity_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['username', ])
        return api.identity_create(username=data['username'], )

    @POST('^/i/b')
    @POST('^/identity/backup/v1$')
    def identity_backup_v1(self, request):
        data = _request_data(request, mandatory_keys=['destination_path', ])
        return api.identity_backup(destination_filepath=data['destination_path'])

    @POST('^/i/r$')
    @POST('^/identity/recover/v1$')
    @POST('^/identity/my/recover/v1$')
    def identity_recover_v1(self, request):
        data = _request_data(request)
        private_key_source = data.get('private_key_source')
        if not private_key_source:
            private_key_local_file = data.get('private_key_local_file')
            if private_key_local_file:
                from system import bpio
                private_key_source = bpio.ReadTextFile(bpio.portablePath(private_key_local_file))
        return api.identity_recover(
            private_key_source=private_key_source,
            known_idurl=data.get('known_idurl'),
        )

    @DELETE('^/i/d$')
    @DELETE('^/identity/delete/v1$')
    @DELETE('^/identity/erase/v1$')
    @DELETE('^/identity/my/delete/v1$')
    @DELETE('^/identity/my/erase/v1$')
    def identity_delete_v1(self, request):
        # TODO: to be implemented
        return api.ERROR('not implemented yet')

    #------------------------------------------------------------------------------

    @GET('^/k/l$')
    @GET('^/key/v1$')
    @GET('^/key/list/v1$')
    def key_list_v1(self, request):
        return api.keys_list(
            sort=bool(_request_arg(request, 'sort', '0') in ['1', 'true', ]),
            include_private=bool(_request_arg(request, 'include_private', '0') in ['1', 'true', ]),
        )

    @GET('^/k/g$')
    @GET('^/key/get/v1$')
    def key_get_v1(self, request):
        return api.key_get(
            key_id=_request_arg(request, 'key_id', mandatory=True),
            include_private=bool(_request_arg(request, 'include_private', '0') in ['1', 'true', ]),
        )

    @POST('^/k/c$')
    @POST('^/key/create/v1$')
    def key_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['alias', ])
        return api.key_create(
            key_alias=data['alias'],
            key_size=int(data.get('size', 2048)),
            include_private=bool(data.get('include_private', '0') in ['1', 'true', ]),
        )

    @DELETE('^/k/d$')
    @DELETE('^/key/delete/v1$')
    @DELETE('^/key/erase/v1$')
    def key_erase_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', ])
        return api.key_erase(key_id=data['key_id'])

    @PUT('^/k/s$')
    @PUT('^/key/share/v1$')
    def key_share_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'trusted_user', ])
        return api.key_share(
            key_id=data['key_id'],
            trusted_global_id_or_idurl=data['trusted_user'],
            include_private=bool(data.get('include_private', '0') in ['1', 'true', ]), )

    @POST('^/k/a$')
    @POST('^/key/audit/v1$')
    def key_audit_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'untrusted_user', ])
        return api.key_audit(
            key_id=data['key_id'],
            untrusted_global_id_or_idurl=data['untrusted_user'],
            is_private=bool(data.get('is_private', '0') in ['1', 'true', ]),
        )

    #------------------------------------------------------------------------------

    @GET('^/f/l$')
    @GET('^/file/v1$')
    @GET('^/file/list/v1$')
    def file_list_v1(self, request):
        return api.files_list(
            remote_path=_request_arg(request, 'remote_path', None),
            key_id=_request_arg(request, 'key_id', None),
            recursive=bool(_request_arg(request, 'recursive', '0') in ['1', 'true', ]),
            all_customers=bool(_request_arg(request, 'all_customers', '0') in ['1', 'true', ]),
            include_uploads=bool(_request_arg(request, 'include_uploads', '0') in ['1', 'true', ]),
            include_downloads=bool(_request_arg(request, 'include_downloads', '0') in ['1', 'true', ]),
        )

    @GET('^/f/l/a$')
    @GET('^/file/list/all/v1$')
    def file_list_all_v1(self, request):
        return api.files_list(all_customers=True, include_uploads=True, include_downloads=True)

    @GET('^/f/i$')
    @GET('^/file/info/v1$')
    def file_info_v1(self, request):
        return api.file_info(
            remote_path=_request_arg(request, 'remote_path', mandatory=True),
            include_uploads=bool(_request_arg(request, 'include_uploads', '1') in ['1', 'true', ]),
            include_downloads=bool(_request_arg(request, 'include_downloads', '1') in ['1', 'true', ]),
        )

    @GET('^/f/s$')
    @GET('^/file/sync/v1$')
    def file_sync_v1(self, request):
        return api.files_sync()

    @POST('^/f/c$')
    @POST('^/file/create/v1$')
    def file_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_create(
            remote_path=data['remote_path'],
            as_folder=bool(data.get('as_folder', '0') in ['1', 'true', ]),
        )

    @DELETE('^/f/d$')
    @DELETE('^/file/delete/v1$')
    def file_delete_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_delete(remote_path=data['remote_path'])

    @GET('^/f/u/l$')
    @GET('^/file/upload/v1$')
    def files_uploads_v1(self, request):
        return api.files_uploads(
            include_running=bool(_request_arg(request, 'include_running', '1') in ['1', 'true', ]),
            include_pending=bool(_request_arg(request, 'include_pending', '1') in ['1', 'true', ]),
        )

    @POST('^/f/u/o$')
    @POST('^/file/upload/open/v1$')
    @POST('^/file/upload/start/v1$')
    def file_upload_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['local_path', 'remote_path', ])
        return api.file_upload_start(
            local_path=data['local_path'],
            remote_path=data['remote_path'],
            wait_result=bool(data.get('wait_result', '0') in ['1', 'true', ]),
            open_share=bool(data.get('open_share', '0') in ['1', 'true', ]),
        )

    @POST('^/f/u/c$')
    @POST('^/file/upload/close/v1$')
    @POST('^/file/upload/stop/v1$')
    def file_upload_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_upload_stop(remote_path=data['remote_path'])

    @GET('^/f/d/l$')
    @GET('^/file/download/v1$')
    def files_downloads_v1(self, request):
        return api.files_downloads()

    @POST('^/f/d/o$')
    @POST('^/file/download/open/v1$')
    @POST('^/file/download/start/v1$')
    def file_download_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_download_start(
            remote_path=data['remote_path'],
            destination_path=data.get('destination_folder', None),
            wait_result=bool(data.get('wait_result', '0') in ['1', 'true', ]),
            open_share=bool(data.get('open_share', '1') in ['1', 'true', ]),
        )

    @POST('^/f/d/c$')
    @POST('^/file/download/close/v1$')
    @POST('^/file/download/stop/v1$')
    def file_download_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_download_stop(remote_path=data['remote_path'])

    @GET('^/f/e$')
    @GET('^/file/explore/v1$')
    def file_explore_v1(self, request):
        return api.file_explore(local_path=_request_arg(request, 'local_path', mandatory=True))

    #------------------------------------------------------------------------------

    @GET('^/sh/l$')
    @GET('^/share/list/v1$')
    def share_list_v1(self, request):
        return api.share_list(
            only_active=bool(_request_arg(request, 'active', '0') in ['1', 'true', ]),
            include_mine=bool(_request_arg(request, 'mine', '1') in ['1', 'true', ]),
            include_granted=bool(_request_arg(request, 'granted', '1') in ['1', 'true', ]),
        )

    @POST('^/sh/c$')
    @POST('^/share/create/v1$')
    def share_create_v1(self, request):
        data = _request_data(request)
        return api.share_create(
            owner_id=data.get('owner_id', None),
            key_size=int(data.get('key_size', '2048')),
        )

    @PUT('^/sh/g$')
    @PUT('^/share/grant/v1$')
    def share_grant_v1(self, request):
        data = _request_data(request, mandatory_keys=[('trusted_global_id', 'trusted_idurl', 'trusted_id', ), 'key_id', ])
        return api.share_grant(
            trusted_remote_user=data.get('trusted_global_id') or data.get('trusted_idurl') or data.get('trusted_id'),
            key_id=data['key_id'],
            timeout=data.get('timeout', 30),
        )

    @POST('^/sh/o$')
    @POST('^/share/open/v1$')
    def share_open_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', ])
        return api.share_open(
            key_id=data['key_id'],
        )

    @DELETE('^/sh/c$')
    @DELETE('^/share/close/v1$')
    def share_close_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', ])
        return api.share_close(
            key_id=data['key_id'],
        )

    @GET('^/sh/h$')
    @GET('^/share/history/v1$')
    def share_history_v1(self, request):
        return api.share_history()

    #------------------------------------------------------------------------------

    @GET('^/fr/l$')
    @GET('^/friend/v1$')
    @GET('^/friend/list/v1$')
    def friend_list_v1(self, request):
        return api.friend_list()

    @POST('^/fr/a$')
    @POST('^/friend/add/v1$')
    def friend_add_v1(self, request):
        data = _request_data(request, mandatory_keys=[('idurl', 'global_id', 'id', ), ])
        return api.friend_add(
            idurl_or_global_id=data.get('global_id') or data.get('idurl') or data.get('id'),
            alias=data.get('alias', ''),
        )

    @DELETE('^/fr/d$')
    @DELETE('^/friend/delete/v1$')
    @DELETE('^/friend/remove/v1$')
    def friend_remove_v1(self, request):
        data = _request_data(request, mandatory_keys=[('idurl', 'global_id', 'id', ), ])
        return api.friend_remove(
            idurl_or_global_id=data.get('global_id') or data.get('idurl') or data.get('id'),
        )

    #------------------------------------------------------------------------------

    @GET('^/sp/d$')
    @GET('^/space/donated/v1$')
    def space_donated_v1(self, request):
        return api.space_donated()

    @GET('^/sp/c$')
    @GET('^/space/consumed/v1$')
    def space_consumed_v1(self, request):
        return api.space_consumed()

    @GET('^/sp/l$')
    @GET('^/space/local/v1$')
    def space_local_v1(self, request):
        return api.space_local()

    #------------------------------------------------------------------------------

    @GET('^/su/l$')
    @GET('^/supplier/v1$')
    @GET('^/supplier/list/v1$')
    def supplier_list_v1(self, request):
        return api.suppliers_list(
            customer_idurl_or_global_id=_request_arg(request, 'customer_id') or _request_arg(request, 'customer_idurl') or _request_arg(request, 'id'),
            verbose=bool(_request_arg(request, 'verbose', '0') in ['1', 'true', ]),
        )

    @DELETE('^/su/r$')
    @DELETE('^/supplier/rotate/v1$')
    @DELETE('^/supplier/replace/v1$')
    @POST('^/supplier/rotate/v1$')
    @POST('^/supplier/replace/v1$')
    def supplier_replace_v1(self, request):
        data = _request_data(request, mandatory_keys=[('index', 'position', 'idurl', 'global_id', 'id', ), ])
        return api.supplier_replace(
            index_or_idurl_or_global_id=(
                data.get('index') or
                data.get('position') or
                data.get('global_id') or
                data.get('idurl') or
                data.get('id')
            ),
        )

    @PUT('^/su/sw$')
    @PUT('^/supplier/switch/v1$')
    def supplier_switch_v1(self, request):
        data = _request_data(request, mandatory_keys=[('index', 'idurl', 'global_id', ), ('new_idurl', 'new_global_id', ), ])
        return api.supplier_change(
            index_or_idurl_or_global_id=data.get('index') or data.get('global_id') or data.get('idurl') or data.get('id'),
            new_supplier_idurl_or_global_id=data.get('new_global_id') or data.get('new_idurl') or data.get('new_id'),
        )

    @POST('^/su/png$')
    @POST('^/supplier/ping/v1$')
    def supplier_ping_v1(self, request):
        return api.suppliers_ping()

    @GET('^/su/dht$')
    @GET('^/supplier/list/dht/v1$')
    def supplier_dht_list_v1(self, request):
        return api.suppliers_dht_lookup(
            customer_idurl_or_global_id=_request_arg(request, 'customer_id') or _request_arg(request, 'customer_idurl') or _request_arg(request, 'id'),
        )

    #------------------------------------------------------------------------------

    @GET('^/cu/l$')
    @GET('^/customer/v1$')
    @GET('^/customer/list/v1$')
    def customer_list_v1(self, request):
        return api.customers_list()

    @DELETE('^/cu/d$')
    @DELETE('^/customer/delete/v1$')
    @DELETE('^/customer/reject/v1$')
    def customer_reject_v1(self, request):
        data = _request_data(request, mandatory_keys=[('idurl', 'global_id', 'id', ), ])
        return api.customer_reject(
            idurl_or_global_id=data.get('global_id') or data.get('idurl') or data.get('id'),
        )

    @POST('^/cu/png$')
    @POST('^/customer/ping/v1$')
    def customer_ping_v1(self, request):
        return api.customers_ping()

    #------------------------------------------------------------------------------

    @GET('^/us/s/(?P<nickname>[^/]+)/$')
    @GET('^/user/search/(?P<nickname>[^/]+)/v1$')
    def user_search_v1(self, request, nickname):
        return api.user_search(nickname, attempts=int(_request_arg(request, 'attempts', 1)))

    @GET('^/us/o/(?P<nickname>[^/]+)/$')
    @GET('^/user/observe/(?P<nickname>[^/]+)/v1$')
    def user_observe_v1(self, request, nickname):
        return api.user_observe(nickname, attempts=int(_request_arg(request, 'attempts', 3)))

    @GET('^/us/o$')
    @GET('^/user/observe/v1$')
    def user_observe_arg_v1(self, request):
        return api.user_observe(
            nickname=_request_arg(request, 'name', mandatory=True),
            attempts=int(_request_arg(request, 'attempts', 3)),
        )

    @GET('^/us/st$')
    @GET('^/user/status/v1$')
    def user_status_v1(self, request):
        return api.user_status(
            idurl_or_global_id=_request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id')
        )

    @GET('^/us/st/c$')
    @GET('^/user/status/check/v1$')
    def user_status_check_v1(self, request):
        return api.user_status_check(
            idurl_or_global_id=_request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id'),
            timeout=_request_arg(request, 'timeout', 5),
        )

    @POST('^/us/png$')
    @POST('^/user/ping/v1$')
    def user_ping_v1(self, request):
        data = _request_data(request, mandatory_keys=[('idurl', 'global_id', 'id', ), ])
        return api.user_ping(
            idurl_or_global_id=data.get('global_id') or data.get('idurl') or data.get('id'),
            timeout=data.get('timeout', 10),
            retries=data.get('retries', 2),
        )

    @GET('^/us/png$')
    @GET('^/user/ping/v1$')
    def user_ping_get_v1(self, request):
        return api.user_ping(
            idurl_or_global_id=_request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id'),
            timeout=_request_arg(request, 'timeout', 10),
            retries=_request_arg(request, 'retries', 2),
        )

    #------------------------------------------------------------------------------
    @GET('^/msg/h?')
    @GET('^/message/history/v1$')
    def message_history_v1(self, request):
        user_identity = _request_arg(request, 'id', None, True)
        return api.message_history(user=user_identity)

    @GET('^/msg/r/(?P<consumer_id>[^/]+)/$')
    @GET('^/message/receive/(?P<consumer_id>[^/]+)/v1$')
    def message_receive_v1(self, request, consumer_id):
        return api.message_receive(consumer_id=consumer_id)

    @POST('^/msg/s$')
    @POST('^/message/send/v1$')
    def message_send_v1(self, request):
        data = _request_data(request, mandatory_keys=[('idurl', 'global_id', 'id', ), 'data', ])
        return api.message_send(
            recipient=data.get('global_id') or data.get('idurl') or data.get('id'),
            json_data=data['data'],
            timeout=data.get('timeout', 5),
        )

    #------------------------------------------------------------------------------

    @GET('^/st/l$')
    @GET('^/state/v1$')
    @GET('^/state/list/v1$')
    @GET('^/automat/v1$')
    @GET('^/automat/list/v1$')
    def automat_list_v1(self, request):
        return api.automats_list()

    #------------------------------------------------------------------------------

    @GET('^/svc/l$')
    @GET('^/service/v1$')
    @GET('^/service/list/v1$')
    def service_list_v1(self, request):
        return api.services_list(
            show_configs=bool(_request_arg(request, 'config', '0') in ['1', 'true', ]),
        )

    @GET('^/svc/i/(?P<service_name>[^/]+)/$')
    @GET('^/service/info/(?P<service_name>[^/]+)/v1$')
    def service_info_v1(self, request, service_name):
        return api.service_info(service_name)

    @POST('^/svc/o/(?P<service_name>[^/]+)/$')
    @POST('^/service/open/(?P<service_name>[^/]+)/v1$')
    @POST('^/service/start/(?P<service_name>[^/]+)/v1$')
    def service_start_v1(self, request, service_name):
        return api.service_start(service_name)

    @POST('^/svc/c/(?P<service_name>[^/]+)/$')
    @POST('^/service/close/(?P<service_name>[^/]+)/v1$')
    @POST('^/service/stop/(?P<service_name>[^/]+)/v1$')
    def service_stop_v1(self, request, service_name):
        return api.service_stop(service_name)

    @POST('^/svc/r/(?P<service_name>[^/]+)/$')
    @POST('^/service/restart/(?P<service_name>[^/]+)/v1$')
    def service_restart_v1(self, request, service_name):
        return api.service_restart(
            service_name=service_name,
            wait_timeout=_request_data(request).get('wait_timeout', 10),
        )

    #------------------------------------------------------------------------------

    @GET('^/pkt/l$')
    @GET('^/packet/v1$')
    @GET('^/packet/list/v1$')
    def packet_list_v1(self, request):
        return api.packets_list()

    @GET('^/pkt/i$')
    @GET('^/packet/info/v1$')
    @GET('^/packet/stats/v1$')
    def packet_stats_v1(self, request):
        return api.packets_stats()

    #------------------------------------------------------------------------------

    @GET('^/tr/l$')
    @GET('^/transfer/v1$')
    @GET('^/transfer/list/v1$')
    def transfers_list_v1(self, request):
        return api.transfers_list()

    #------------------------------------------------------------------------------

    @GET('^/con/l$')
    @GET('^/connection/v1$')
    @GET('^/connection/list/v1$')
    def connection_list_v1(self, request):
        return api.connections_list()

    #------------------------------------------------------------------------------

    @GET('^/str/l$')
    @GET('^/stream/v1$')
    @GET('^/stream/list/v1$')
    def stream_list_v1(self, request):
        return api.streams_list()

    #------------------------------------------------------------------------------

    @GET('^/qu/l$')
    @GET('^/queue/v1$')
    @GET('^/queue/list/v1$')
    def queue_list_v1(self, request):
        return api.queue_list()

    #------------------------------------------------------------------------------

    @POST('^/ev/s/(?P<event_id>[^/]+)/$')
    @POST('^/event/send/(?P<event_id>[^/]+)/v1$')
    def event_send_v1(self, request, event_id):
        return api.event_send(event_id, json_data=_request_data(request,))

    @GET('^/ev/l/(?P<consumer_id>[^/]+)/$')
    @GET('^/event/listen/(?P<consumer_id>[^/]+)/v1$')
    def event_listen_v1(self, request, consumer_id):
        return api.events_listen(consumer_id)

    #------------------------------------------------------------------------------

    @GET('^/nw/rcon$')
    @GET('^/network/reconnect/v1$')
    def network_reconnect_v1(self, request):
        return api.network_reconnect()

    @GET('^/nw/stn$')
    @GET('^/network/stun/v1$')
    def network_stun_v1(self, request):
        return api.network_stun(
            udp_port=int(_request_arg(request, 'udp_port', 0)) or None,
            dht_port=int(_request_arg(request, 'dht_port', 0)) or None,
        )

    @GET('^/nw/con$')
    @GET('^/network/connected/v1$')
    def network_connected_v1(self, request):
        return api.network_connected(wait_timeout=int(_request_arg(request, 'wait_timeout', '5')))

    @GET('^/nw/st$')
    @GET('^/network/status/v1$')
    def network_status_v1(self, request):
        return api.network_status(
            show_suppliers=bool(_request_arg(request, 'suppliers', '0') in ['1', 'true', ]),
            show_customers=bool(_request_arg(request, 'customers', '0') in ['1', 'true', ]),
            show_cache=bool(_request_arg(request, 'cache', '0') in ['1', 'true', ]),
            show_tcp=bool(_request_arg(request, 'tcp', '0') in ['1', 'true', ]),
            show_udp=bool(_request_arg(request, 'udp', '0') in ['1', 'true', ]),
            show_proxy=bool(_request_arg(request, 'proxy', '0') in ['1', 'true', ]),
        )

    @GET('^/nw/i$')
    @GET('^/network/info/v1$')
    @GET('^/network/details/v1$')
    def network_details_v1(self, request):
        return api.network_status(
            show_suppliers=bool(_request_arg(request, 'suppliers', '1') in ['1', 'true', ]),
            show_customers=bool(_request_arg(request, 'customers', '1') in ['1', 'true', ]),
            show_cache=bool(_request_arg(request, 'cache', '1') in ['1', 'true', ]),
            show_tcp=bool(_request_arg(request, 'tcp', '1') in ['1', 'true', ]),
            show_udp=bool(_request_arg(request, 'udp', '1') in ['1', 'true', ]),
            show_proxy=bool(_request_arg(request, 'proxy', '1') in ['1', 'true', ]),
        )

    #------------------------------------------------------------------------------

    @GET('^/d/v/g$')
    @GET('^/dht/node/find/v1$')
    def dht_node_find_v1(self, request):
        return api.dht_node_find(node_id_64=_request_arg(request, 'dht_id', mandatory=False, default=None))

    @GET('^/d/v/g$')
    @GET('^/dht/value/get/v1$')
    def dht_value_get_v1(self, request):
        return api.dht_value_get(
            key=_request_arg(request, 'key', mandatory=True),
            record_type=_request_arg(request, 'record_type', mandatory=False, default='skip_validation'),
        )

    @POST('^/d/v/s$')
    @POST('^/dht/value/set/v1$')
    def dht_value_set_v1(self, request):
        data = _request_data(request, mandatory_keys=['key', 'value', ])
        return api.dht_value_set(
            key=data['key'],
            value=data['value'],
            expire=data.get('expire', None),
            record_type=data.get('record_type', 'skip_validation'),
        )

    @GET('^/d/d/d$')
    @GET('^/dht/db/dump/v1$')
    def dht_db_dump_v1(self, request):
        return api.dht_local_db_dump()

    #------------------------------------------------------------------------------

    @ALL('^/*')
    def zzz_not_found(self, request):
        return api.ERROR('method %s:%s was not found' % (request.method, request.path))

    #------------------------------------------------------------------------------
