#!/usr/bin/python
# api_rest_http_server.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
from six import PY2

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 12

_APILogFileEnabled = False

#------------------------------------------------------------------------------

import os
import sys
import time

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport
from twisted.web.server import Site  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.interface import api

from bitdust.lib import strng
from bitdust.lib import jsn
from bitdust.lib import serialization

from bitdust.system import local_fs

from bitdust.main import settings

from bitdust_forks.txrestapi.txrestapi.json_resource import JsonAPIResource, _JsonResource
from bitdust_forks.txrestapi.txrestapi.methods import GET, POST, PUT, DELETE, ALL

#------------------------------------------------------------------------------

_APIListener = None
_APISecret = None

#------------------------------------------------------------------------------

YES = ('1', 'true', 'True', 'yes', 'Yes', 'YES', 'ok', 1, True)

#------------------------------------------------------------------------------


def init(port=None):
    global _APIListener
    global _APILogFileEnabled

    _APILogFileEnabled = settings.config.conf().getBool('logs/api-enabled')

    if _APIListener is not None:
        lg.warn('_APIListener already initialized')
        return

    if not port:
        port = 8180

    read_api_secret()

    current_recursionlimit = None
    if PY2:
        current_recursionlimit = sys.getrecursionlimit()
        sys.setrecursionlimit(2000)

    serve_http(port)
    # serve_https(port)

    if PY2:
        sys.setrecursionlimit(current_recursionlimit)

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


def read_api_secret():
    global _APISecret
    _APISecret = local_fs.ReadTextFile(settings.APISecretFile())


def serve_https(port):
    global _APIListener
    from bitdust.crypt import certificate

    # server private key
    if os.path.exists(settings.APIServerCertificateKeyFile()):
        server_key_pem = local_fs.ReadBinaryFile(settings.APIServerCertificateKeyFile())
        server_key = certificate.load_private_key(server_key_pem)
    else:
        server_key, server_key_pem = certificate.generate_private_key()
        local_fs.WriteBinaryFile(settings.APIServerCertificateKeyFile(), server_key_pem)
    # server certificate
    if os.path.exists(settings.APIServerCertificateFile()):
        server_cert_pem = local_fs.ReadBinaryFile(settings.APIServerCertificateFile())
    else:
        server_cert_pem = certificate.generate_self_signed_cert(
            hostname=u'localhost',
            ip_addresses=[u'127.0.0.1'],
            server_key=server_key,
        )
        local_fs.WriteBinaryFile(settings.APIServerCertificateFile(), server_cert_pem)
    # client private key
    if os.path.exists(settings.APIClientCertificateKeyFile()):
        client_key_pem = local_fs.ReadBinaryFile(settings.APIClientCertificateKeyFile())
        client_key = certificate.load_private_key(client_key_pem)
    else:
        client_key, client_key_pem = certificate.generate_private_key()
        local_fs.WriteBinaryFile(settings.APIClientCertificateKeyFile(), client_key_pem)
    # client certificate
    if os.path.exists(settings.APIClientCertificateFile()):
        client_cert_pem = local_fs.ReadBinaryFile(settings.APIClientCertificateFile())
        ca_cert_pem = local_fs.ReadBinaryFile(settings.APIServerCertificateFile())
    else:
        ca_cert_pem = local_fs.ReadBinaryFile(settings.APIServerCertificateFile())
        ca_cert = certificate.load_certificate(ca_cert_pem)
        client_cert_pem = certificate.generate_csr_client_cert(
            hostname=u'localhost',
            server_ca_cert=ca_cert,
            server_key=server_key,
            client_key=client_key,
        )
        local_fs.WriteBinaryFile(settings.APIClientCertificateFile(), client_cert_pem)

    try:
        from twisted.internet import ssl  # @UnresolvedImport
        api_resource = BitDustRESTHTTPServer()
        site = BitDustAPISite(api_resource, timeout=None)
        auth = ssl.Certificate.loadPEM(server_cert_pem)
        cert = ssl.PrivateCertificate.loadPEM(server_cert_pem + server_key_pem)
        _APIListener = reactor.listenSSL(port, site, cert.options(auth), interface='127.0.0.1')  # @UndefinedVariable
    except:
        lg.exc()
        os._exit(1)


def serve_http(port):
    global _APIListener
    try:
        api_resource = BitDustRESTHTTPServer()
        site = BitDustAPISite(api_resource, timeout=None)
        _APIListener = reactor.listenTCP(port, site)  # @UndefinedVariable
    except:
        lg.exc()
        os._exit(1)


#------------------------------------------------------------------------------


def _request_arg(request, key, default='', mandatory=False):
    """
    Simplify extracting arguments from url query in request.
    """
    args = request.args or {}
    if key in args:
        values = args.get(key, [default])
        return strng.to_text(values[0]) if values else default
    if strng.to_bin(key) in args:
        values = args.get(strng.to_bin(key), [default])
        return strng.to_text(values[0]) if values else default
    if mandatory:
        raise Exception('mandatory url query argument missed: %s' % key)
    return default


def _request_data(request, mandatory_keys=[], default_value={}):
    """
    Simplify extracting input parameters from request body.
    """
    try:
        input_request_data = request.content.getvalue()
    except:
        input_request_data = request.content.read()
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


def _input_value(json_data, keys_list, default_value=None):
    """
    Helper method.
    """
    for key in keys_list:
        if key in json_data:
            return json_data[key]
    return default_value


def _index_or_idurl_or_global_id(
    data,
    index_fields=['index', 'position', 'pos'],
    id_fields=['global_id', 'idurl', 'id'],
):
    """
    Helper method.
    """
    value = _input_value(data, index_fields)
    if value is None:
        value = _input_value(data, id_fields)
    return value


#------------------------------------------------------------------------------


class BitDustAPISite(Site):

    def buildProtocol(self, addr):
        """
        Only accepting connections from local machine!
        """
        if addr.host != '127.0.0.1':
            lg.err('refused connection from remote host: %r' % addr.host)
            return None
        return Site.buildProtocol(self, addr)


class BitDustRESTHTTPServer(JsonAPIResource):

    """
    A set of API method to interract and control locally running BitDust process.
    """

    #------------------------------------------------------------------------------

    def getChild(self, name, request):
        global _APISecret
        if _APISecret:
            api_secret_header = request.getHeader('api_secret')
            if api_secret_header != _APISecret:
                return _JsonResource(
                    dict(status='ERROR', errors=['access denied']),
                    time.time(),
                )
        return JsonAPIResource.getChild(self, name, request)

    def log_request(self, request, callback, args):
        if not callback:
            return None
        uri = request.uri.decode()
        try:
            func_name = callback.im_func.func_name
        except:
            func_name = callback.__name__
        _args = jsn.dict_items_to_text(request.args)
        if not _args:
            _args = _request_data(request)
        else:
            _args = {k: (v[0] if (v and isinstance(v, list)) else v) for k, v in _args.items()}
        if _Debug:
            if uri not in [
                '/v1/event/listen/electron',
                '/v1/network/connected',
                '/v1/process/health',
                '/event/listen/electron/v1',
                '/network/connected/v1',
                '/process/health/v1',
            ] or _DebugLevel > 10:
                lg.out(_DebugLevel, '*** %s:%s  API HTTP  %s(%r)' % (request.method.decode(), uri, func_name, _args))
        if _APILogFileEnabled:
            lg.out(0, '*** %s:%s  HTTP  %s(%r)' % (request.method.decode(), uri, func_name, _args), log_name='api', showtime=True)
        return None

    #------------------------------------------------------------------------------

    @GET('^/p/st$')
    @GET('^/v1/process/stop$')
    @GET('^/process/stop/v1$')
    def process_stop_v1(self, request):
        return api.process_stop(instant=bool(_request_arg(request, 'instant', '1') in YES))

    @GET('^/p/rst$')
    @GET('^/v1/process/restart$')
    @GET('^/process/restart/v1$')
    def process_restart_v1(self, request):
        return api.process_restart()

    @GET('^/p/h$')
    @GET('^/v1/process/health$')
    @GET('^/process/health/v1$')
    def process_health_v1(self, request):
        return api.process_health()

    @GET('^/p/h$')
    @GET('^/v1/process/info$')
    @GET('^/process/info/v1$')
    def process_info_v1(self, request):
        return api.process_info()

    @GET('^/p/d$')
    @GET('^/v1/process/debug$')
    @GET('^/process/debug/v1$')
    def process_debug_v1(self, request):
        return api.process_debug()

    #------------------------------------------------------------------------------

    @GET('^/dev/l$')
    @GET('^/v1/device/list$')
    @GET('^/device/list/v1$')
    def device_list_v1(self, request):
        return api.devices_list()

    @GET('^/dev/i$')
    @GET('^/v1/device/info$')
    @GET('^/device/info/v1$')
    def device_info_v1(self, request):
        return api.device_info(name=_request_arg(request, 'name', mandatory=True))

    @POST('^/dev/a$')
    @POST('^/v1/device/add$')
    @POST('^/device/add/v1$')
    def device_add_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.device_add(
            name=data['name'],
            routed=bool(data.get('routed', '0') in YES),
            activate=bool(data.get('activate', '0') in YES),
            web_socket_port=int(data['web_socket_port']) if 'web_socket_port' in data else None,
            key_size=int(data['key_size']) if 'key_size' in data else None,
        )

    @POST('^/dev/o$')
    @POST('^/v1/device/start$')
    @POST('^/device/start/v1$')
    def device_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.device_start(
            name=data['name'],
            wait_listening=bool(data.get('wait_listening', '0') in YES),
        )

    @POST('^/dev/a/r$')
    @POST('^/v1/device/authorization/reset$')
    @POST('^/device/authorization/reset/v1$')
    def device_authorization_reset_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.device_authorization_reset(
            name=data['name'],
            start=bool(data.get('start', '1') in YES),
            wait_listening=bool(data.get('wait_listening', '0') in YES),
        )

    @POST('^/dev/a/cc$')
    @POST('^/v1/device/authorization/client_code$')
    @POST('^/device/authorization/client_code/v1$')
    def device_authorization_client_code_v1(self, request):
        data = _request_data(request, mandatory_keys=['name', 'client_code'])
        return api.device_authorization_client_code(
            name=data['name'],
            client_code=data['client_code'],
        )

    @POST('^/dev/c$')
    @POST('^/v1/device/stop$')
    @POST('^/device/stop/v1$')
    def device_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.device_stop(name=data['name'])

    @DELETE('^/dev/d$')
    @DELETE('^/v1/device/remove$')
    @DELETE('^/device/remove/v1$')
    def device_remove_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.device_remove(name=data['name'])

    @GET('^/dev/r/i$')
    @GET('^/v1/device/router/info$')
    @GET('^/device/router/info/v1$')
    def device_router_info_v1(self, request):
        return api.device_router_info()

    #------------------------------------------------------------------------------

    @POST('^/nw/cr$')
    @POST('^/network/create')
    @POST('^/network/create/v1$')
    def network_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['url'])
        return api.network_create(url=data['url'])

    @POST('^/nw/sel$')
    @POST('^/network/select')
    @POST('^/network/select/v1$')
    def network_select_v1(self, request):
        data = _request_data(request, mandatory_keys=['name'])
        return api.network_select(name=data['name'])

    @GET('^/nw/con$')
    @GET('^/v1/network/connected$')
    @GET('^/network/connected/v1$')
    def network_connected_v1(self, request):
        return api.network_connected(wait_timeout=int(_request_arg(request, 'wait_timeout', '10')))

    @GET('^/nw/dcon$')
    @GET('^/v1/network/disconnect')
    @GET('^/network/disconnect/v1$')
    def network_disconnect_v1(self, request):
        return api.network_disconnect()

    @GET('^/nw/rcon$')
    @GET('^/v1/network/reconnect$')
    @GET('^/network/reconnect/v1$')
    def network_reconnect_v1(self, request):
        return api.network_reconnect()

    @GET('^/nw/st$')
    @GET('^/v1/network/status$')
    @GET('^/network/status/v1$')
    def network_status_v1(self, request):
        return api.network_status(
            suppliers=bool(_request_arg(request, 'suppliers', '0') in YES),
            customers=bool(_request_arg(request, 'customers', '0') in YES),
            cache=bool(_request_arg(request, 'cache', '0') in YES),
            tcp=bool(_request_arg(request, 'tcp', '0') in YES),
            udp=bool(_request_arg(request, 'udp', '0') in YES),
            proxy=bool(_request_arg(request, 'proxy', '0') in YES),
            dht=bool(_request_arg(request, 'dht', '0') in YES),
        )

    @GET('^/nw/i$')
    @GET('^/v1/network/info$')
    @GET('^/v1/network/details$')
    @GET('^/network/info/v1$')
    @GET('^/network/details/v1$')
    def network_info_v1(self, request):
        return api.network_status(
            suppliers=bool(_request_arg(request, 'suppliers', '1') in YES),
            customers=bool(_request_arg(request, 'customers', '1') in YES),
            cache=bool(_request_arg(request, 'cache', '1') in YES),
            tcp=bool(_request_arg(request, 'tcp', '1') in YES),
            udp=bool(_request_arg(request, 'udp', '1') in YES),
            proxy=bool(_request_arg(request, 'proxy', '1') in YES),
            dht=bool(_request_arg(request, 'dht', '1') in YES),
        )

    @GET('^/nw/cf$')
    @GET('^/v1/network/configuration$')
    @GET('^/network/configuration/v1$')
    def network_configuration_v1(self, request):
        return api.network_configuration()

    @GET('^/nw/stn$')
    @GET('^/v1/network/stun$')
    @GET('^/network/stun/v1$')
    def network_stun_v1(self, request):
        return api.network_stun(
            udp_port=int(_request_arg(request, 'udp_port', 0)) or None,
            dht_port=int(_request_arg(request, 'dht_port', 0)) or None,
        )

    #------------------------------------------------------------------------------

    @GET('^/c/l$')
    @GET('^/v1/config/list$')
    @GET('^/config/list/v1$')
    def config_list_v1(self, request):
        return api.configs_list(
            sort=bool(_request_arg(request, 'sort', '0') in YES),
            include_info=bool(_request_arg(request, 'include_info', '0') in YES),
        )

    @GET('^/c/t$')
    @GET('^/v1/config/tree$')
    @GET('^/config/tree/v1$')
    def configs_tree_v1(self, request):
        return api.configs_tree(include_info=bool(_request_arg(request, 'include_info', '0') in YES))

    @GET('^/c/g/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/$')
    @GET('^/v1/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)$')
    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_get_l3_v1(self, request, key1, key2, key3):
        return api.config_get(key=(key1 + '/' + key2 + '/' + key3), include_info=bool(_request_arg(request, 'include_info', '0') in YES))

    @GET('^/c/g/(?P<key1>[^/]+)/(?P<key2>[^/]+)/$')
    @GET('^/v1/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)$')
    @GET('^/config/get/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_get_l2_v1(self, request, key1, key2):
        return api.config_get(key=(key1 + '/' + key2), include_info=bool(_request_arg(request, 'include_info', '0') in YES))

    @GET('^/c/g/(?P<key>[^/]+)/$')
    @GET('^/v1/config/get/(?P<key>[^/]+)$')
    @GET('^/config/get/(?P<key>[^/]+)/v1$')
    def config_get_l1_v1(self, request, key):
        return api.config_get(key=key, include_info=bool(_request_arg(request, 'include_info', '0') in YES))

    @GET('^/c/g$')
    @GET('^/v1/config/get$')
    @GET('^/config/get/v1$')
    def config_get_v1(self, request):
        return api.config_get(key=_request_arg(request, 'key', mandatory=True), include_info=bool(_request_arg(request, 'include_info', '0') in YES))

    @POST('^/c/s/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/$')
    @POST('^/v1/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)$')
    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/(?P<key3>[^/]+)/v1$')
    def config_set_l3_v1(self, request, key1, key2, key3):
        data = _request_data(request, mandatory_keys=['value'])
        return api.config_set(key=(key1 + '/' + key2 + '/' + key3), value=data['value'])

    @POST('^/c/s/(?P<key1>[^/]+)/(?P<key2>[^/]+)/$')
    @POST('^/v1/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)$')
    @POST('^/config/set/(?P<key1>[^/]+)/(?P<key2>[^/]+)/v1$')
    def config_set_l2_v1(self, request, key1, key2):
        data = _request_data(request, mandatory_keys=['value'])
        return api.config_set(key=(key1 + '/' + key2), value=data['value'])

    @POST('^/c/s/(?P<key>[^/]+)/$')
    @POST('^/v1/config/set/(?P<key>[^/]+)$')
    @POST('^/config/set/(?P<key>[^/]+)/v1$')
    def config_set_l1_v1(self, request, key):
        data = _request_data(request, mandatory_keys=['value'])
        return api.config_set(key=key, value=data['value'])

    @POST('^/c/s$')
    @POST('^/v1/config/set$')
    @POST('^/config/set/v1$')
    def config_set_v1(self, request):
        data = _request_data(request, mandatory_keys=['key', 'value'])
        return api.config_set(key=data['key'], value=data['value'])

    #------------------------------------------------------------------------------

    @GET('^/i/g$')
    @GET('^/v1/identity/get$')
    @GET('^/identity/get/v1$')
    def identity_get_v1(self, request):
        return api.identity_get(include_xml_source=bool(_request_arg(request, 'xml_source', '0') in YES))

    @POST('^/i/c$')
    @POST('^/v1/identity/create$')
    @POST('^/identity/create/v1$')
    def identity_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['username'])
        return api.identity_create(username=data['username'], join_network=bool(data.get('join_network', '0') in YES))

    @POST('^/i/b$')
    @POST('^/identity/backup$')
    @POST('^/identity/backup/v1$')
    def identity_backup_v1(self, request):
        data = _request_data(request, mandatory_keys=['destination_filepath'])
        return api.identity_backup(destination_filepath=data['destination_filepath'])

    @POST('^/i/r$')
    @POST('^/v1/identity/recover$')
    @POST('^/identity/recover/v1$')
    def identity_recover_v1(self, request):
        data = _request_data(request)
        private_key_source = data.get('private_key_source')
        if not private_key_source:
            private_key_local_file = data.get('private_key_local_file')
            if private_key_local_file:
                from bitdust.system import bpio
                private_key_source = bpio.ReadTextFile(bpio.portablePath(private_key_local_file))
        return api.identity_recover(
            private_key_source=private_key_source,
            known_idurl=data.get('known_idurl'),
            join_network=bool(data.get('join_network', '0') in YES),
        )

    @DELETE('^/i/d$')
    @DELETE('^/v1/identity/erase$')
    @DELETE('^/identity/erase/v1$')
    def identity_erase_v1(self, request):
        data = _request_data(request)
        return api.identity_erase(erase_private_key=data.get('erase_private_key', False))

    @PUT('^/i/rot$')
    @PUT('^/v1/identity/rotate$')
    @PUT('^/identity/rotate/v1$')
    def identity_rotate_v1(self, request):
        return api.identity_rotate()

    @PUT('^/i/h$')
    @PUT('^/v1/identity/heal$')
    @PUT('^/identity/heal/v1$')
    def identity_heal_v1(self, request):
        return api.ERROR('not implemented yet')

    @GET('^/i/ch/l$')
    @GET('^/v1/identity/cache/list$')
    @GET('^/identity/cache/list/v1$')
    def identity_list_v1(self, request):
        return api.identity_cache_list()

    #------------------------------------------------------------------------------

    @GET('^/k/l$')
    @GET('^/v1/key/list$')
    @GET('^/key/list/v1$')
    def key_list_v1(self, request):
        return api.keys_list(
            sort=bool(_request_arg(request, 'sort', '0') in YES),
            include_private=bool(_request_arg(request, 'include_private', '0') in YES),
        )

    @GET('^/k/g$')
    @GET('^/v1/key/get$')
    @GET('^/key/get/v1$')
    def key_get_v1(self, request):
        return api.key_get(
            key_id=_request_arg(request, 'key_id', mandatory=True),
            include_private=bool(_request_arg(request, 'include_private', '0') in YES),
            include_signature=bool(_request_arg(request, 'include_signature', '0') in YES),
            generate_signature=bool(_request_arg(request, 'generate_signature', '0') in YES),
        )

    @POST('^/k/c$')
    @POST('^/v1/key/create$')
    @POST('^/key/create/v1$')
    def key_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['alias'])
        return api.key_create(
            key_alias=data['alias'],
            key_size=int(data['key_size']) if 'key_size' in data else None,
            label=data.get('label', ''),
            active=bool(data.get('active', '1') in YES),
            include_private=bool(data.get('include_private', '0') in YES),
        )

    @POST('^/k/lb$')
    @POST('^/v1/key/label$')
    @POST('^/key/label/v1$')
    def key_label_v1(self, request):
        data = _request_data(request, mandatory_keys=['label', 'key_id'])
        return api.key_label(key_id=data['key_id'], label=data['label'])

    @POST('^/k/st$')
    @POST('^/v1/key/state$')
    @POST('^/key/state/v1$')
    def key_state_v1(self, request):
        data = _request_data(request, mandatory_keys=['active', 'key_id'])
        return api.key_label(key_id=data['key_id'], active=bool(data.get('active', '1') in YES))

    @DELETE('^/k/d$')
    @DELETE('^/v1/key/erase$')
    @DELETE('^/key/erase/v1$')
    def key_erase_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id'])
        return api.key_erase(key_id=data['key_id'])

    @PUT('^/k/s$')
    @PUT('^/v1/key/share$')
    @PUT('^/key/share/v1$')
    def key_share_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'trusted_user_id'])
        return api.key_share(
            key_id=data['key_id'],
            trusted_user_id=data['trusted_user_id'],
            include_private=bool(data.get('include_private', '0') in YES),
            include_signature=bool(data.get('include_signature', '0') in YES),
        )

    @POST('^/k/a$')
    @POST('^/v1/key/audit$')
    @POST('^/key/audit/v1$')
    def key_audit_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id', 'untrusted_user_id'])
        return api.key_audit(
            key_id=data['key_id'],
            untrusted_user_id_id=data['untrusted_user_id'],
            is_private=bool(data.get('is_private', '0') in YES),
        )

    #------------------------------------------------------------------------------

    @GET('^/f/s$')
    @GET('^/v1/file/sync$')
    @GET('^/file/sync/v1$')
    def file_sync_v1(self, request):
        return api.files_sync(force=bool(_request_arg(request, 'force', '0') in YES), )

    @GET('^/f/l$')
    @GET('^/v1/file/list$')
    @GET('^/file/list/v1$')
    def file_list_v1(self, request):
        return api.files_list(
            remote_path=_request_arg(request, 'remote_path', None),
            key_id=_request_arg(request, 'key_id', None),
            recursive=bool(_request_arg(request, 'recursive', '0') in YES),
            all_customers=bool(_request_arg(request, 'all_customers', '0') in YES),
            include_uploads=bool(_request_arg(request, 'uploads', '0') in YES),
            include_downloads=bool(_request_arg(request, 'downloads', '0') in YES),
        )

    @GET('^/f/l/a$')
    @GET('^/v1/file/list/all$')
    @GET('^/file/list/all/v1$')
    def file_list_all_v1(self, request):
        return api.files_list(all_customers=True, include_uploads=True, include_downloads=True)

    @GET('^/f/e$')
    @GET('^/v1/file/exists$')
    @GET('^/file/exists/v1$')
    def file_exists_v1(self, request):
        return api.file_exists(remote_path=_request_arg(request, 'remote_path', mandatory=True))

    @GET('^/f/i$')
    @GET('^/v1/file/info$')
    @GET('^/file/info/v1$')
    def file_info_v1(self, request):
        return api.file_info(
            remote_path=_request_arg(request, 'remote_path', mandatory=True),
            include_uploads=bool(_request_arg(request, 'uploads', '1') in YES),
            include_downloads=bool(_request_arg(request, 'downloads', '1') in YES),
        )

    @POST('^/f/c$')
    @POST('^/v1/file/create$')
    @POST('^/file/create/v1$')
    def file_create_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path'])
        return api.file_create(
            remote_path=data['remote_path'],
            as_folder=bool(data.get('as_folder', '0') in YES),
        )

    @DELETE('^/f/d$')
    @DELETE('^/v1/file/delete$')
    @DELETE('^/file/delete/v1$')
    def file_delete_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path'])
        return api.file_delete(remote_path=data['remote_path'])

    @GET('^/f/u/l$')
    @GET('^/v1/file/upload$')
    @GET('^/file/upload/v1$')
    def files_uploads_v1(self, request):
        return api.files_uploads(
            include_running=bool(_request_arg(request, 'running', '1') in YES),
            include_pending=bool(_request_arg(request, 'pending', '1') in YES),
        )

    @POST('^/f/u/o$')
    @POST('^/v1/file/upload/start$')
    @POST('^/file/upload/start/v1$')
    def file_upload_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['local_path', 'remote_path'])
        return api.file_upload_start(
            local_path=data['local_path'],
            remote_path=data['remote_path'],
            wait_result=bool(data.get('wait_result', '0') in YES),
            publish_events=bool(data.get('publish_events', '0') in YES),
        )

    @POST('^/f/u/c$')
    @POST('^/v1/file/upload/stop$')
    @POST('^/file/upload/stop/v1$')
    def file_upload_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path'])
        return api.file_upload_stop(remote_path=data['remote_path'])

    @GET('^/f/d/l$')
    @GET('^/v1/file/download$')
    @GET('^/file/download/v1$')
    def files_downloads_v1(self, request):
        return api.files_downloads()

    @POST('^/f/d/o$')
    @POST('^/v1/file/download/start$')
    @POST('^/file/download/start/v1$')
    def file_download_start_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path'])
        return api.file_download_start(
            remote_path=data['remote_path'],
            destination_path=data.get('destination_folder', None),
            wait_result=bool(data.get('wait_result', '0') in YES),
            publish_events=bool(data.get('publish_events', '0') in YES),
        )

    @POST('^/f/d/c$')
    @POST('^/v1/file/download/stop$')
    @POST('^/file/download/stop/v1$')
    def file_download_stop_v1(self, request):
        data = _request_data(request, mandatory_keys=['remote_path'])
        return api.file_download_stop(remote_path=data['remote_path'])

    @GET('^/f/x$')
    @GET('^/v1/file/explore$')
    @GET('^/file/explore/v1$')
    def file_explore_v1(self, request):
        return api.file_explore(local_path=_request_arg(request, 'local_path', mandatory=True))

    #------------------------------------------------------------------------------

    @GET('^/sh/l$')
    @GET('^/v1/share/list$')
    @GET('^/share/list/v1$')
    def share_list_v1(self, request):
        return api.shares_list(
            only_active=bool(_request_arg(request, 'active', '0') in YES),
            include_mine=bool(_request_arg(request, 'mine', '1') in YES),
            include_granted=bool(_request_arg(request, 'granted', '1') in YES),
        )

    @GET('^/sh/i$')
    @GET('^/v1/share/info$')
    @GET('^/share/info/v1$')
    def share_info_v1(self, request):
        return api.share_info(key_id=_request_arg(request, 'key_id', mandatory=True))

    @POST('^/sh/c$')
    @POST('^/v1/share/create$')
    @POST('^/share/create/v1$')
    def share_create_v1(self, request):
        data = _request_data(request)
        return api.share_create(
            owner_id=data.get('owner_id', None),
            key_size=int(data['key_size']) if 'key_size' in data else None,
            label=data.get('label', ''),
            active=bool(data.get('active', '1') in YES),
        )

    @DELETE('^/sh/d$')
    @DELETE('^/v1/share/delete$')
    @DELETE('^/share/delete/v1$')
    def share_delete_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id'])
        return api.share_delete(key_id=data['key_id'])

    @PUT('^/sh/g$')
    @PUT('^/v1/share/grant$')
    @PUT('^/share/grant/v1$')
    def share_grant_v1(self, request):
        data = _request_data(request, mandatory_keys=[
            ('trusted_user_id', 'trusted_global_id', 'trusted_idurl', 'trusted_id'),
            'key_id',
        ])
        return api.share_grant(
            key_id=data['key_id'],
            trusted_user_id=data.get('trusted_user_id') or data.get('trusted_global_id') or data.get('trusted_idurl') or data.get('trusted_id'),
            timeout=data.get('timeout', 30),
            publish_events=bool(data.get('publish_events', '0') in YES),
        )

    @POST('^/sh/o$')
    @POST('^/v1/share/open$')
    @POST('^/share/open/v1$')
    def share_open_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id'])
        return api.share_open(
            key_id=data['key_id'],
            publish_events=bool(data.get('publish_events', '0') in YES),
        )

    @DELETE('^/sh/cl$')
    @DELETE('^/v1/share/close$')
    @DELETE('^/share/close/v1$')
    def share_close_v1(self, request):
        data = _request_data(request, mandatory_keys=['key_id'])
        return api.share_close(key_id=data['key_id'])

    @GET('^/sh/h$')
    @GET('^/v1/share/history$')
    @GET('^/share/history/v1$')
    def share_history_v1(self, request):
        return api.share_history()

    #------------------------------------------------------------------------------

    @GET('^/gr/l$')
    @GET('^/v1/group/list$')
    @GET('^/group/list/v1$')
    def group_list_v1(self, request):
        return api.groups_list()

    @POST('^/gr/c$')
    @POST('^/v1/group/create$')
    @POST('^/group/create/v1$')
    def group_create_v1(self, request):
        data = _request_data(request)
        return api.group_create(
            creator_id=data.get('creator_id', None),
            key_size=int(data['key_size']) if 'key_size' in data else None,
            label=data.get('label', ''),
            timeout=data.get('timeout', 20),
        )

    @GET('^/gr/i$')
    @GET('^/v1/group/info$')
    @GET('^/group/info/v1$')
    def group_info_v1(self, request):
        return api.group_info(group_key_id=_request_arg(request, 'group_key_id'))

    @GET('^/gr/dht$')
    @GET('^/v1/group/info/dht$')
    @GET('^/group/info/dht/v1$')
    def group_info_dht_v1(self, request):
        return api.group_info_dht(group_creator_id=_request_arg(request, 'group_creator_id') or _request_arg(request, 'group_creator_idurl') or _request_arg(request, 'id'))

    @POST('^/gr/j$')
    @POST('^/v1/group/join$')
    @POST('^/group/join/v1$')
    def group_join_v1(self, request):
        data = _request_data(request, mandatory_keys=['group_key_id'])
        return api.group_join(
            group_key_id=data['group_key_id'],
            publish_events=bool(data.get('publish_events', '0') in YES),
            use_dht_cache=bool(data.get('use_dht_cache', '0') in YES),
            wait_result=bool(data.get('wait_result', '1') in YES),
        )

    @DELETE('^/gr/lv$')
    @DELETE('^/v1/group/leave$')
    @DELETE('^/group/leave/v1$')
    def group_leave_v1(self, request):
        data = _request_data(request, mandatory_keys=['group_key_id'])
        return api.group_leave(
            group_key_id=data['group_key_id'],
            erase_key=data.get('erase_key', False),
        )

    @PUT('^/gr/r$')
    @PUT('^/v1/group/reconnect$')
    @PUT('^/group/reconnect/v1$')
    def group_reconnect_v1(self, request):
        data = _request_data(request, mandatory_keys=['group_key_id'])
        return api.group_reconnect(
            group_key_id=data['group_key_id'],
            use_dht_cache=bool(data.get('use_dht_cache', '0') in YES),
        )

    @PUT('^/gr/sh$')
    @PUT('^/v1/group/share$')
    @PUT('^/group/share/v1$')
    def group_share_v1(self, request):
        data = _request_data(request, mandatory_keys=[
            ('trusted_user_id', 'trusted_global_id', 'trusted_idurl', 'trusted_id'),
            'group_key_id',
        ])
        return api.group_share(
            group_key_id=data['group_key_id'],
            trusted_user_id=data.get('trusted_user_id') or data.get('trusted_global_id') or data.get('trusted_idurl') or data.get('trusted_id'),
            timeout=data.get('timeout', 45),
            publish_events=bool(data.get('publish_events', '0') in YES),
        )

    #------------------------------------------------------------------------------

    @GET('^/fr/l$')
    @GET('^/v1/friend/list$')
    @GET('^/friend/list/v1$')
    def friend_list_v1(self, request):
        return api.friends_list()

    @POST('^/fr/a$')
    @POST('^/v1/friend/add$')
    @POST('^/friend/add/v1$')
    def friend_add_v1(self, request):
        data = _request_data(request, mandatory_keys=[('trusted_user_id', 'idurl', 'global_id', 'id')])
        return api.friend_add(
            trusted_user_id=data.get('trusted_user_id') or data.get('global_id') or data.get('idurl') or data.get('id'),
            alias=data.get('alias', ''),
        )

    @DELETE('^/fr/d$')
    @DELETE('^/v1/friend/remove$')
    @DELETE('^/friend/remove/v1$')
    def friend_remove_v1(self, request):
        data = _request_data(request, mandatory_keys=[('user_id', 'idurl', 'global_id', 'id')])
        return api.friend_remove(user_id=data.get('user_id') or data.get('global_id') or data.get('idurl') or data.get('id'))

    #------------------------------------------------------------------------------

    @POST('^/us/png$')
    @POST('^/v1/user/ping$')
    @POST('^/user/ping/v1$')
    def user_ping_v1(self, request):
        data = _request_data(request, mandatory_keys=[('user_id', 'idurl', 'global_id', 'id')])
        return api.user_ping(
            user_id=data.get('user_id') or data.get('global_id') or data.get('idurl') or data.get('id'),
            timeout=data.get('timeout', 15),
            retries=data.get('retries', 2),
        )

    @GET('^/us/png$')
    @GET('^/v1/user/ping$')
    @GET('^/user/ping/v1$')
    def user_ping_get_v1(self, request):
        return api.user_ping(
            user_id=_request_arg(request, 'user_id') or _request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id'),
            timeout=_request_arg(request, 'timeout', 15),
            retries=_request_arg(request, 'retries', 2),
        )

    @GET('^/us/st$')
    @GET('^/v1/user/status$')
    @GET('^/user/status/v1$')
    def user_status_v1(self, request):
        return api.user_status(user_id=_request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id'))

    @GET('^/us/st/c$')
    @GET('^/v1/user/status/check$')
    @GET('^/user/status/check/v1$')
    def user_status_check_v1(self, request):
        return api.user_status_check(
            user_id=_request_arg(request, 'user_id') or _request_arg(request, 'global_id') or _request_arg(request, 'idurl') or _request_arg(request, 'id'),
            timeout=_request_arg(request, 'timeout', 15),
        )

    @GET('^/us/s/(?P<nickname>[^/]+)/$')
    @GET('^/v1/user/search/(?P<nickname>[^/]+)$')
    @GET('^/user/search/(?P<nickname>[^/]+)/v1$')
    def user_search_v1(self, request, nickname):
        return api.user_search(nickname, attempts=int(_request_arg(request, 'attempts', 1)))

    @GET('^/us/s$')
    @GET('^/v1/user/search$')
    @GET('^/user/search/v1$')
    def user_search_arg_v1(self, request):
        return api.user_search(
            nickname=_request_arg(request, 'nickname', mandatory=True),
            attempts=int(_request_arg(request, 'attempts', 1)),
        )

    @GET('^/us/o/(?P<nickname>[^/]+)/$')
    @GET('^/v1/user/observe/(?P<nickname>[^/]+)$')
    @GET('^/user/observe/(?P<nickname>[^/]+)/v1$')
    def user_observe_v1(self, request, nickname):
        return api.user_observe(
            nickname=nickname,
            attempts=int(_request_arg(request, 'attempts', 3)),
        )

    @GET('^/us/o$')
    @GET('^/v1/user/observe$')
    @GET('^/user/observe/v1$')
    def user_observe_arg_v1(self, request):
        return api.user_observe(
            nickname=_request_arg(request, 'nickname', mandatory=True),
            attempts=int(_request_arg(request, 'attempts', 3)),
        )

    #------------------------------------------------------------------------------

    @GET('^/msg/h$')
    @GET('^/v1/message/history$')
    @GET('^/message/history/v1$')
    def message_history_v1(self, request):
        return api.message_history(
            recipient_id=_request_arg(request, 'id', None, True),
            sender_id=_request_arg(request, 'sender_id', None, False),
            message_type=_request_arg(request, 'message_type', 'private_message'),
            offset=int(_request_arg(request, 'offset', '0')),
            limit=int(_request_arg(request, 'limit', '100')),
        )

    @GET('^/msg/c$')
    @GET('^/v1/message/conversation$')
    @GET('^/message/conversation/v1$')
    def message_conversation_v1(self, request):
        return api.message_conversations_list(
            message_types=list(filter(None,
                                      _request_arg(request, 'message_types', '').split(','))),
            offset=int(_request_arg(request, 'offset', '0')),
            limit=int(_request_arg(request, 'limit', '100')),
        )

    @GET('^/msg/r/(?P<consumer_callback_id>[^/]+)/$')
    @GET('^/v1/message/receive/(?P<consumer_callback_id>[^/]+)$')
    @GET('^/message/receive/(?P<consumer_callback_id>[^/]+)/v1$')
    def message_receive_v1(self, request, consumer_callback_id):
        return api.message_receive(
            consumer_callback_id=consumer_callback_id,
            direction=_request_arg(request, 'direction', 'incoming'),
            message_types=_request_arg(request, 'message_types', 'private_message,group_message'),
            polling_timeout=int(_request_arg(request, 'polling_timeout', 60, False)),
        )

    @POST('^/msg/s$')
    @POST('^/v1/message/send$')
    @POST('^/message/send/v1$')
    def message_send_v1(self, request):
        data = _request_data(request, mandatory_keys=[
            ('recipient_id', 'idurl', 'global_id', 'id'),
            'data',
        ])
        return api.message_send(
            recipient_id=data.get('recipient_id') or data.get('global_id') or data.get('idurl') or data.get('id'),
            data=data['data'],
            ping_timeout=data.get('ping_timeout', 30),
            message_ack_timeout=data.get('message_ack_timeout', 15),
        )

    @POST('^/msg/sg$')
    @POST('^/v1/message/send/group$')
    @POST('^/message/send/group/v1$')
    def message_send_group_v1(self, request):
        data = _request_data(request, mandatory_keys=['group_key_id', 'data'])
        return api.message_send_group(group_key_id=data.get('group_key_id'), data=data['data'])

    #------------------------------------------------------------------------------

    @GET('^/su/l$')
    @GET('^/v1/supplier/list$')
    @GET('^/supplier/list/v1$')
    def supplier_list_v1(self, request):
        return api.suppliers_list(
            customer_id=_request_arg(request, 'customer_id') or _request_arg(request, 'customer_idurl') or _request_arg(request, 'id'),
            verbose=bool(_request_arg(request, 'verbose', '0') in YES),
        )

    @POST('^/su/c$')
    @POST('^/v1/supplier/change')
    @POST('^/supplier/change/v1$')
    def supplier_change_v1(self, request):
        data = _request_data(request)
        return api.supplier_change(
            position=_input_value(data, ['position', 'pos', 'index'], None),
            supplier_id=data.get('supplier_id') or data.get('supplier_idurl') or data.get('supplier_glob_id'),
            new_supplier_id=data.get('new_global_id') or data.get('new_idurl') or data.get('new_supplier_id'),
        )

    @DELETE('^/su/r$')
    @DELETE('^/v1/supplier/replace$')
    @DELETE('^/supplier/replace/v1$')
    def supplier_replace_v1(self, request):
        data = _request_data(request)
        return api.supplier_change(
            position=_input_value(data, ['position', 'pos', 'index'], None),
            supplier_id=data.get('supplier_id') or data.get('supplier_idurl') or data.get('supplier_glob_id'),
            new_supplier_id=None,
        )

    @PUT('^/su/sw$')
    @PUT('^/v1/supplier/switch$')
    @PUT('^/supplier/switch/v1$')
    def supplier_switch_v1(self, request):
        data = _request_data(request, mandatory_keys=[('new_idurl', 'new_global_id', 'new_supplier_id')])
        return api.supplier_change(
            position=_input_value(data, ['position', 'pos', 'index'], None),
            supplier_id=data.get('supplier_id') or data.get('supplier_idurl') or data.get('supplier_glob_id'),
            new_supplier_id=data.get('new_global_id') or data.get('new_idurl') or data.get('new_supplier_id'),
        )

    @POST('^/su/png$')
    @POST('^/v1/supplier/ping$')
    @POST('^/supplier/ping/v1$')
    def supplier_ping_v1(self, request):
        return api.suppliers_ping()

    @GET('^/su/dht$')
    @GET('^/v1/supplier/list/dht$')
    @GET('^/supplier/list/dht/v1$')
    def suppliers_list_dht(self, request):
        return api.suppliers_list_dht(customer_id=_request_arg(request, 'customer_id') or _request_arg(request, 'customer_idurl') or _request_arg(request, 'id'))

    #------------------------------------------------------------------------------

    @GET('^/cu/l$')
    @GET('^/v1/customer/list$')
    @GET('^/customer/list/v1$')
    def customer_list_v1(self, request):
        return api.customers_list()

    @DELETE('^/cu/d$')
    @DELETE('^/v1/customer/reject$')
    @DELETE('^/customer/reject/v1$')
    def customer_reject_v1(self, request):
        data = _request_data(request, mandatory_keys=[('customer_id', 'idurl', 'global_id', 'id')])
        return api.customer_reject(
            customer_id=data.get('customer_id') or data.get('global_id') or data.get('idurl') or data.get('id'),
            erase_customer_key=bool(_request_arg(request, 'erase_customer_key', '1') in YES),
        )

    @POST('^/cu/png$')
    @POST('^/v1/customer/ping$')
    @POST('^/customer/ping/v1$')
    def customer_ping_v1(self, request):
        return api.customers_ping()

    #------------------------------------------------------------------------------

    @GET('^/sp/d$')
    @GET('^/v1/space/donated$')
    @GET('^/space/donated/v1$')
    def space_donated_v1(self, request):
        return api.space_donated()

    @GET('^/sp/c$')
    @GET('^/v1/space/consumed$')
    @GET('^/space/consumed/v1$')
    def space_consumed_v1(self, request):
        return api.space_consumed()

    @GET('^/sp/l$')
    @GET('^/v1/space/local$')
    @GET('^/space/local/v1$')
    def space_local_v1(self, request):
        return api.space_local()

    #------------------------------------------------------------------------------

    @GET('^/svc/l$')
    @GET('^/v1/service/list$')
    @GET('^/service/list/v1$')
    def service_list_v1(self, request):
        return api.services_list(with_configs=bool(_request_arg(request, 'with_configs', '0') in YES))

    @GET('^/svc/i/(?P<service_name>[^/]+)/$')
    @GET('^/v1/service/info/(?P<service_name>[^/]+)$')
    @GET('^/service/info/(?P<service_name>[^/]+)/v1$')
    def service_info_v1(self, request, service_name):
        return api.service_info(service_name)

    @POST('^/svc/o/(?P<service_name>[^/]+)/$')
    @POST('^/v1/service/start/(?P<service_name>[^/]+)$')
    @POST('^/service/start/(?P<service_name>[^/]+)/v1$')
    def service_start_v1(self, request, service_name):
        return api.service_start(service_name)

    @POST('^/svc/c/(?P<service_name>[^/]+)/$')
    @POST('^/v1/service/stop/(?P<service_name>[^/]+)$')
    @POST('^/service/stop/(?P<service_name>[^/]+)/v1$')
    def service_stop_v1(self, request, service_name):
        return api.service_stop(service_name)

    @POST('^/svc/r/(?P<service_name>[^/]+)/$')
    @POST('^/v1/service/restart/(?P<service_name>[^/]+)$')
    @POST('^/service/restart/(?P<service_name>[^/]+)/v1$')
    def service_restart_v1(self, request, service_name):
        return api.service_restart(
            service_name=service_name,
            wait_timeout=_request_data(request).get('wait_timeout', 15),
        )

    @GET('^/svc/h/(?P<service_name>[^/]+)/$')
    @GET('^/v1/service/health/(?P<service_name>[^/]+)$')
    @GET('^/service/health/(?P<service_name>[^/]+)/v1$')
    def service_health_v1(self, request, service_name):
        return api.service_health(service_name)

    #------------------------------------------------------------------------------

    @GET('^/pkt/l$')
    @GET('^/v1/packet/list$')
    @GET('^/packet/list/v1$')
    def packet_list_v1(self, request):
        return api.packets_list()

    @GET('^/pkt/i$')
    @GET('^/v1/packet/info$')
    @GET('^/v1/packet/stats$')
    @GET('^/packet/info/v1$')
    @GET('^/packet/stats/v1$')
    def packet_stats_v1(self, request):
        return api.packets_stats()

    #------------------------------------------------------------------------------

    @GET('^/tr/l$')
    @GET('^/v1/transfer/list$')
    @GET('^/transfer/list/v1$')
    def transfer_list_v1(self, request):
        return api.transfers_list()

    @GET('^/con/l$')
    @GET('^/v1/connection/list$')
    @GET('^/connection/list/v1$')
    def connection_list_v1(self, request):
        return api.connections_list(protocols=map(strng.to_text, filter(None, _request_arg(request, 'protocols', '').strip().lower().split(','))) or None)

    @GET('^/str/l$')
    @GET('^/v1/stream/list$')
    @GET('^/stream/list/v1$')
    def stream_list_v1(self, request):
        return api.streams_list(protocols=map(strng.to_text, filter(None, _request_arg(request, 'protocols', '').strip().lower().split(','))) or None)

    #------------------------------------------------------------------------------

    @GET('^/qu/l$')
    @GET('^/v1/queue/list$')
    @GET('^/queue/list/v1$')
    def queue_list_v1(self, request):
        return api.queues_list()

    @GET('^/qu/c/l$')
    @GET('^/v1/queue/consumer/list$')
    @GET('^/queue/consumer/list/v1$')
    def queue_consumer_list_v1(self, request):
        return api.queue_consumers_list()

    @GET('^/qu/p/l$')
    @GET('^/v1/queue/producer/list$')
    @GET('^/queue/producer/list/v1$')
    def queue_producer_list_v1(self, request):
        return api.queue_producers_list()

    @GET('^/qu/k/l$')
    @GET('^/v1/queue/keeper/list$')
    @GET('^/queue/keeper/list/v1$')
    def queue_keeper_list_v1(self, request):
        return api.queue_keepers_list()

    @GET('^/qu/ped/l$')
    @GET('^/v1/queue/peddler/list$')
    @GET('^/queue/peddler/list/v1$')
    def queue_peddler_list_v1(self, request):
        return api.queue_peddlers_list()

    @GET('^/qu/s/l$')
    @GET('^/v1/queue/stream/list$')
    @GET('^/queue/stream/list/v1$')
    def queue_stream_list_v1(self, request):
        return api.queue_streams_list()

    #------------------------------------------------------------------------------

    @GET('^/ev/l$')
    @GET('^/v1/event/list$')
    @GET('^/event/list/v1$')
    def event_list_v1(self, request):
        return api.events_list()

    @POST('^/ev/s/(?P<event_id>[^/]+)/$')
    @POST('^/v1/event/send/(?P<event_id>[^/]+)$')
    @POST('^/event/send/(?P<event_id>[^/]+)/v1$')
    def event_send_v1(self, request, event_id):
        return api.event_send(event_id, data=_request_data(request))

    @GET('^/ev/l/(?P<consumer_callback_id>[^/]+)/$')
    @GET('^/v1/event/listen/(?P<consumer_callback_id>[^/]+)$')
    @GET('^/event/listen/(?P<consumer_callback_id>[^/]+)/v1$')
    def event_listen_v1(self, request, consumer_callback_id):
        return api.event_listen(consumer_callback_id=consumer_callback_id)

    #------------------------------------------------------------------------------

    @GET('^/d/n/f$')
    @GET('^/v1/dht/node/find$')
    @GET('^/dht/node/find/v1$')
    def dht_node_find_v1(self, request):
        return api.dht_node_find(
            node_id_64=_request_arg(request, 'node_id_64', mandatory=False, default=None) or _request_arg(request, 'dht_id', mandatory=False, default=None),
            layer_id=int(_request_arg(request, 'layer_id', mandatory=False, default=0)),
        )

    @GET('^/d/u/r$')
    @GET('^/v1/dht/user/random$')
    @GET('^/dht/user/random/v1$')
    def dht_user_random_v1(self, request):
        return api.dht_user_random(
            layer_id=int(_request_arg(request, 'layer_id', mandatory=False, default=0)),
            count=int(_request_arg(request, 'count', mandatory=False, default=1)),
        )

    @GET('^/d/v/g$')
    @GET('^/v1/dht/value/get$')
    @GET('^/dht/value/get/v1$')
    def dht_value_get_v1(self, request):
        return api.dht_value_get(
            key=_request_arg(request, 'key', mandatory=True),
            record_type=_request_arg(request, 'record_type', mandatory=False, default='skip_validation'),
            layer_id=int(_request_arg(request, 'layer_id', mandatory=False, default=0)),
        )

    @POST('^/d/v/s$')
    @POST('^/v1/dht/value/set$')
    @POST('^/dht/value/set/v1$')
    def dht_value_set_v1(self, request):
        data = _request_data(request, mandatory_keys=['key', 'value'])
        return api.dht_value_set(
            key=data['key'],
            value=data['value'],
            expire=data.get('expire', None),
            record_type=data.get('record_type', 'skip_validation'),
            layer_id=int(data.get('layer_id', 0)),
        )

    @GET('^/d/d/d$')
    @GET('^/v1/dht/db/dump$')
    @GET('^/dht/db/dump/v1$')
    def dht_db_dump_v1(self, request):
        return api.dht_local_db_dump()

    #------------------------------------------------------------------------------

    @GET('^/b/i$')
    @GET('^/v1/blockchain/info$')
    @GET('^/blockchain/info/v1$')
    def blockchain_info(self, request):
        return api.blockchain_info()

    @GET('^/b/w/b$')
    @GET('^/v1/blockchain/wallet/balance$')
    @GET('^/blockchain/wallet/balance/v1$')
    def blockchain_wallet_balance(self, request):
        return api.blockchain_wallet_balance()

    @POST('^/b/t/s$')
    @POST('^/v1/blockchain/transaction/send$')
    @POST('^/blockchain/transaction/send/v1$')
    def blockchain_transaction_send(self, request):
        data = _request_data(request, mandatory_keys=['recipient', 'amount'])
        return api.blockchain_transaction_send(
            recipient=data['recipient'],
            amount=data['amount'],
            operation=data.get('operation', '') or '',
            data=data.get('data', '') or '',
        )

    @GET('^/b/b/p$')
    @GET('^/v1/blockchain/block/produce$')
    @GET('^/blockchain/block/produce/v1$')
    def blockchain_block_produce(self, request):
        return api.blockchain_block_produce()

    #------------------------------------------------------------------------------

    @GET('^/st/l$')
    @GET('^/v1/state/list$')
    @GET('^/v1/automat/list$')
    @GET('^/state/list/v1$')
    @GET('^/automat/list/v1$')
    def automat_list_v1(self, request):
        return api.automats_list()

    @GET('^/st/i$')
    @GET('^/v1/state/info$')
    @GET('^/v1/automat/info$')
    @GET('^/state/info/v1$')
    @GET('^/automat/info/v1$')
    def automat_info_v1(self, request):
        return api.automat_info(
            index=_request_arg(request, 'index', default=None, mandatory=False),
            automat_id=_request_arg(request, 'automat_id', default=None, mandatory=False),
        )

    @POST('^/st/e/start$')
    @POST('^/v1/state/events/start$')
    @POST('^/v1/automat/events/start$')
    @POST('^/state/events/start/v1$')
    @POST('^/automat/events/start/v1$')
    def automat_events_start_v1(self, request):
        data = _request_data(request)
        return api.automat_events_start(
            index=data.get('index', None),
            automat_id=data.get('automat_id', None),
            state_unchanged=bool(data.get('state_unchanged', '0') in YES),
        )

    @POST('^/st/e/stop$')
    @POST('^/v1/state/events/stop$')
    @POST('^/v1/automat/events/stop$')
    @POST('^/state/events/stop/v1$')
    @POST('^/automat/events/stop/v1$')
    def automat_events_stop_v1(self, request):
        data = _request_data(request)
        return api.automat_events_stop(
            index=data.get('index', None),
            automat_id=data.get('automat_id', None),
        )

    #------------------------------------------------------------------------------

    @ALL('^/*')
    def zzz_not_found(self, request):
        """
        This method is intended to return an error message when requested method was not found.
        Started with "zzz" because stuff is sorted alphabetically - so just to be able to put the regex on last place.
        """
        return api.ERROR('method %s:%s was not found' % (request.method, request.path))

    #------------------------------------------------------------------------------
