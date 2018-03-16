#!/usr/bin/python
# api_rest_http_server.py
#
# Copyright (C) 2008-2018 Veselin Penev, https://bitdust.io
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

import cgi
import json

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.web.server import Site

#------------------------------------------------------------------------------

from logs import lg

from interface import api

from lib.txrestapi.txrestapi.resource import APIResource
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
        _APIListener = reactor.listenTCP(port, site)
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
        return values[0] if values else default
    if mandatory:
        raise Exception('mandatory url query argument missed: %s' % key)
    return default


def _request_data(request, mandatory_keys=[], default_value=None):
    """
    Simplify extracting input parameters from request body.
    """
    input_request_data = request.content.getvalue()
    if not input_request_data:
        if mandatory_keys:
            raise Exception('mandatory json input missed: %s' % mandatory_keys)
        return default_value
    try:
        data = json.loads(request.content.getvalue())
    except:
        raise Exception('invalid json input')
    for k in mandatory_keys:
        if k not in data:
            raise Exception('one of mandatory parameters missed: %s' % mandatory_keys)
    return data

#------------------------------------------------------------------------------

class BitDustAPISite(Site):

    def buildProtocol(self, addr):
        """
        Only accepting connections from local machine!
        """
        if addr.host != '127.0.0.1':
            return None
        return Site.buildProtocol(self, addr)


class BitDustRESTHTTPServer(APIResource):
    """
    A set of API method to interract and control locally running BitDust process.
    """

    #------------------------------------------------------------------------------

    @GET('^/process/stop/v1$')
    def process_stop(self, request):
        return api.stop()

    @GET('^/process/restart/v1$')
    def process_restart(self, request):
        return api.restart(showgui=bool(request.args.get('showgui')))

    @GET('^/process/show/v1$')
    def process_show(self, request):
        return api.show()

    #------------------------------------------------------------------------------

    @GET('^/config/v1$')
    @GET('^/config/list/v1$')
    def config_list_v1(self, request):
        return api.config_list(sort=True)

    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_get_l3_v1(self, request, key1, key2, key3):
        return api.config_get(key=(key1 + '/' + key2 + '/' + key3))

    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_get_l2_v1(self, request, key1, key2):
        return api.config_get(key=(key1 + '/' + key2))

    @GET('^/config/get/(?P<key>[^/]+)/v1$')
    def config_get_l1_v1(self, request, key):
        return api.config_get(key=key)

    @GET('^/config/get/v1$')
    def config_get_v1(self, request):
        return api.config_get(key=cgi.escape(dict({} or request.args).get('key', [''])[0]),)

    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_set_l3_v1(self, request, key1, key2, key3):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=(key1 + '/' + key2 + '/' + key3), value=data['value'])

    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_set_l2_v1(self, request, key1, key2):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=(key1 + '/' + key2), value=data['value'])

    @POST('^/config/set/(?P<key>[^/]+)/v1$')
    def config_set_l1_v1(self, request, key):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=key, value=data['value'])

    @POST('^/config/set/v1$')
    def config_set_v1(self, request):
        data = _request_data(request, mandatory_keys=['value', ])
        return api.config_set(key=data['key'], value=data['value'])

    #------------------------------------------------------------------------------

    @GET('^/identity/get/v1$')
    def identity_get_v1(self, request):
        return api.identity_get(
            include_xml_source=bool(_request_arg(request, 'include_xml_source', '0') in ['1', 'true', ]), )

    @POST('^/identity/create/v1$')
    def identity_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['username', ])
        return api.identity_create(username=data['username'], )

    @POST('^/identity/recover/v1$')
    def identity_recover_v1(self, request):
        data = _request_data(request)
        private_key_source = data.get('private_key_source')
        if not private_key_source:
            private_key_local_file = data.get('private_key_local_file')
            if private_key_local_file:
                from system import bpio
                private_key_source = bpio.ReadBinaryFile(bpio.portablePath(private_key_local_file))
        return api.identity_recover(
            private_key_source=private_key_source,
            known_idurl=data.get('known_idurl'))

    @DELETE('^/identity/delete/v1$')
    def identity_delete_v1(self, request):
        return api

    @GET('^/identity/find/v1$')
    def identity_find_v1(self, request):
        nickname = _request_arg(request, 'nickname', None)
        return api.find_peer_by_nickname(nickname=nickname)

    #------------------------------------------------------------------------------

    @GET('^/key/v1$')
    @GET('^/key/list/v1$')
    def key_list_v1(self, request):
        return api.keys_list(
            sort=bool(_request_arg(request, 'sort', '0') in ['1', 'true', ]),
            include_private=bool(_request_arg(request, 'include_private', '0') in ['1', 'true', ]), )

    @GET('^/key/get/v1$')
    def key_get_v1(self, request):
        return api.key_get(
            key_id=_request_arg(request, 'key_id', mandatory=True),
            include_private=bool(_request_arg(request, 'include_private', '0') in ['1', 'true', ]), )

    @POST('^/key/create/v1$')
    def key_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['alias', ])
        return api.key_create(
            key_alias=data['alias'],
            key_size=int(data.get('size', 4096)),
            include_private=bool(data.get('include_private', '0') in ['1', 'true', ]), )

    @DELETE('^/key/erase/v1$')
    def key_erase_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', ])
        return api.key_erase(key_id=data['key_id'])

    @PUT('^/key/share/v1$')
    def key_share_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'trusted_user', ])
        return api.key_share(
            key_id=data['key_id'],
            trusted_global_id_or_idurl=data['trusted_user'],
            include_private=bool(data.get('include_private', '0') in ['1', 'true', ]), )

    @POST('^/key/audit/v1$')
    def key_audit_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'untrusted_user', ])
        return api.key_audit(
            key_id=data['key_id'],
            untrusted_global_id_or_idurl=data['untrusted_user'],
            is_private=bool(data.get('is_private', '0') in ['1', 'true', ]), )

    #------------------------------------------------------------------------------

    @GET('^/file/sync/v1$')
    def file_sync_v1(self, request):
        return api.files_sync()

    @GET('^/file/v1$')
    @GET('^/file/list/v1$')
    def file_list_v1(self, request):
        return api.files_list(
            remote_path=_request_arg(request, 'remote_path', None),
            key_id=_request_arg(request, 'key_id', None),
            recursive=bool(_request_arg(request, 'recursive', '0') in ['1', 'true', ]), )

    @GET('^/file/info/v1$')
    def file_info_v1(self, request):
        return api.file_info(
            remote_path=_request_arg(request, 'remote_path', mandatory=True),
            include_uploads=bool(_request_arg(request, 'include_uploads', '1') in ['1', 'true', ]),
            include_downloads=bool(_request_arg(request, 'include_downloads', '1') in ['1', 'true', ]), )

    @POST('^/file/create/v1$')
    def file_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_create(
            remote_path=data['remote_path'],
            as_folder=bool(data.get('as_folder', '0') in ['1', 'true', ]), )

    @DELETE('^/file/delete/v1$')
    def file_delete_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_delete(remote_path=data['remote_path'])

    @GET('^/file/upload/v1$')
    def files_uploads_v1(self, request):
        return api.files_uploads(
            include_running=bool(_request_arg(request, 'include_running', '1') in ['1', 'true', ]),
            include_pending=bool(_request_arg(request, 'include_pending', '1') in ['1', 'true', ]), )

    @POST('^/file/upload/start/v1$')
    def file_upload_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['local_path', 'remote_path', ])
        return api.file_upload_start(
            local_path=data['local_path'],
            remote_path=data['remote_path'],
            wait_result=bool(data.get('wait_result', '0') in ['1', 'true', ]), )

    @POST('^/file/upload/stop/v1$')
    def file_upload_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_upload_stop(remote_path=data['remote_path'])

    @POST('^/file/download/start/v1$')
    def file_download_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_download_start(
            remote_path=data['remote_path'],
            destination_path=data.get('destination_folder', None),
            wait_result=bool(data.get('wait_result', '0') in ['1', 'true', ]), )

    @POST('^/file/download/stop/v1$')
    def file_download_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path', ])
        return api.file_download_stop(remote_path=data['remote_path'])

    @GET('^/file/explore/v1$')
    def file_explore_v1(self, request):
        return api.file_explore(local_path=_request_arg(request, 'local_path', mandatory=True))

    #------------------------------------------------------------------------------

    @GET('^/supplier/v1$')
    @GET('^/supplier/list/v1$')
    def supplier_list(self, request):
        return api.suppliers_list(
            customer_idurl=_request_arg(request, 'customer_id') or _request_arg(request, 'customer_idurl')
        )

    #------------------------------------------------------------------------------

    @GET('^/user/search/(?P<nickname>[^/]+)/v1$')
    def user_search(self, request, nickname):
        return api.user_search(nickname)
    
    @POST('^/user/ping/v1$')
    def user_ping(self, request):
        data = _request_data(request, mandatory_keys=['customer_idurl'])
        return api.user_ping(
            idurl=data['customer_idurl'],
            timeout=data['timeout']
        )

    #------------------------------------------------------------------------------

    @GET('^/friends/v1$')
    def friend_list(self, request):
        return api.user_list()

    @POST('^/friends/add/v1$')
    def friend_add(self, request):
        data = _request_data(request, mandatory_keys=['customer_idurl'])
        return api.user_add(
            idurl=data['customer_idurl'],
            nickname=data['nickname']
        )

    @POST('^/friends/remove/v1$')
    def friend_remove(self, request):
        data = _request_data(request, mandatory_keys=['customer_idurl'])
        return api.user_remove(
            idurl=data['customer_idurl']
        )

    #------------------------------------------------------------------------------

    @GET('^/share/history/v1$')
    def share_history(self, request):
        return api.share_history()

    @POST('^/share/open/v1$')
    def share_open(self, request):
        data = _request_data(request, mandatory_keys=['remote_user', 'key_id', ])
        return api.share_open(remote_user=data['remote_user'], key_id=data['key_id'])

    #------------------------------------------------------------------------------

    @GET('^/service/v1$')
    @GET('^/service/list/v1$')
    def service_list(self, request):
        return api.services_list()

    @GET('^/service/info/(?P<service_name>[^/]+)/v1$')
    def service_info(self, request, service_name):
        return api.service_info(service_name)

    @POST('^/service/start/(?P<service_name>[^/]+)/v1$')
    def service_start(self, request, service_name):
        return api.service_start(service_name)

    @POST('^/service/stop/(?P<service_name>[^/]+)/v1$')
    def service_stop(self, request, service_name):
        return api.service_stop(service_name)

    @POST('^/service/restart/(?P<service_name>[^/]+)/v1$')
    def service_restart(self, request, service_name):
        return api.service_restart(
            service_name, wait_timeout=_request_data(request, default_value={}).get('wait_timeout', 10))

    #------------------------------------------------------------------------------

    @POST('^/event/send/(?P<event_id>[^/]+)/v1$')
    def event_send(self, request, event_id):
        return api.event_send(event_id, json_data=_request_data(request,))

    @GET('^/event/listen/(?P<consumer_id>[^/]+)/v1$')
    def event_listen(self, request, consumer_id):
        return api.events_listen(consumer_id)

    #------------------------------------------------------------------------------

    @GET('^/network/reconnect/v1$')
    def network_reconnect_v1(self, request):
        return api.network_reconnect()

    @GET('^/network/stun/v1$')
    def network_stun_v1(self, request):
        return api.network_stun()

    @GET('^/network/connected/v1$')
    def network_connected_v1(self, request):
        return api.network_connected(wait_timeout=int(_request_arg(request, 'wait_timeout', '5')))

    @GET('^/network/status/v1$')
    def network_status_v1(self, request):
        return api.network_status()

    #------------------------------------------------------------------------------

    @GET('^/packet/v1$')
    @GET('^/packet/list/v1$')
    def packet_list_v1(self, request):
        return api.packets_list()

    @GET('^/packet/stats/v1$')
    def packet_stats_v1(self, request):
        return api.packets_stats()

    #------------------------------------------------------------------------------

    @GET('^/transfer/v1$')
    @GET('^/transfer/list/v1$')
    def transfers_list_v1(self, request):
        return api.transfers_list()

    #------------------------------------------------------------------------------

    @GET('^/connection/v1$')
    @GET('^/connection/list/v1$')
    def connection_list_v1(self, request):
        return api.connections_list()

    #------------------------------------------------------------------------------

    @GET('^/stream/v1$')
    @GET('^/stream/list/v1$')
    def stream_list_v1(self, request):
        return api.streams_list()

    #------------------------------------------------------------------------------

    @GET('^/queue/v1$')
    @GET('^/queue/list/v1$')
    def queue_list_v1(self, request):
        return api.queue_list()

    #------------------------------------------------------------------------------

    @ALL('^/*')
    def not_found(self, request):
        return api.ERROR('method %s:%s not found' % (request.method, request.path))

    #------------------------------------------------------------------------------
