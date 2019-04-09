#!/usr/bin/python
# http_node.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (http_node.py) is part of BitDust Software.
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
.. module:: http_node.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 8

#------------------------------------------------------------------------------

import os
import sys
import time
import base64

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in tcp_node.py')

from twisted.internet import protocol
from twisted.internet.defer import Deferred,succeed
from twisted.internet.error import CannotListenError
from twisted.web.client import HTTPClientFactory
from twisted.web import server, resource

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..', '..')))

#------------------------------------------------------------------------------

from logs import lg

from lib import nameurl
from lib import net_misc
from lib import strng

from system import bpio
from system import tmpfile

from contacts import contactsdb
from contacts import identitycache

from userid import my_id

from main import settings

#------------------------------------------------------------------------------

_Outbox = {}
_Contacts = {}
_Receiver = None
_ReceivingLoop = None
_ServerListener = None
_LastPingTimeDict = {}
_PingDelayDict = {}
_ConnectionsDict = {}
_CurrentDelay = 5

#------------------------------------------------------------------------------


# def init(receiving=True, sending_port=None):
#     """
#     """
#     lg.out(4, 'http_node.init')
#     contactsdb.AddContactsChangedCallback(on_contacts_changed)
#     if sending_port:
#         start_sending(sending_port)
#     if receiving:
#         start_receiving()


# def shutdown():
#     """
#     """
#     contactsdb.RemoveContactsChangedCallback(on_contacts_changed)
#     stop_sending()
#     stop_receiving()

#------------------------------------------------------------------------------

def start_sending(port):
    global _ServerListener

    if _ServerListener is not None:
        lg.out(8, 'http_node.start_http_server is already started')
        return _ServerListener

    lg.out(6, 'http_node.start_http_server going to listen on port ' + str(port))

    site = server.Site(SenderServer())
    try:
        _ServerListener = reactor.listenTCP(int(port), site)
    except:
        lg.exc()
        _ServerListener = None
    return _ServerListener


def stop_sending():
    global _ServerListener
    lg.out(6, 'http_node.stop_sending')
    if _ServerListener is None:
        lg.out(8, 'http_node.stop_sending _ServerListener is None')
        d = Deferred()
        d.callback('')
        return d
    d = _ServerListener.stopListening()
    _ServerListener = None
    return d

#------------------------------------------------------------------------------

def send_file(idurl, filename):
    lg.out(12, 'http_node.send to %s %s' % (idurl, filename))
    global _Outbox
    if idurl not in _Outbox:
        _Outbox[idurl] = []
    _Outbox[idurl].append(filename)
    #we want to keep only 10 last files.
    if len(_Outbox[idurl]) > 10:
        lostedfilename = _Outbox[idurl].pop(0)
        lg.warn('losted: "%s"' % lostedfilename)
#         transport_control.sendStatusReport(
#             'unknown',
#             lostedfilename,
#             'failed',
#             'http',)

#------------------------------------------------------------------------------

class SenderServer(resource.Resource):
    isLeaf = True

    def render_POST(self, request):
        global _Outbox
        idurl = request.getHeader('idurl')
        if idurl is None:
            return ''
        lg.out(14, 'http_node.SenderServer.render connection from ' + idurl)
        if idurl not in list(_Outbox.keys()):
            return ''
        r = ''
        for filename in _Outbox[idurl]:
            if not os.path.isfile(filename):
                continue
            if not os.access(filename, os.R_OK):
                continue
            src = bpio.ReadBinaryFile(filename)
            if src == '':
                continue
            src64 = base64.b64encode(src)
            r += src64 + '\n'
            lg.out(12, 'http_node.SenderServer.render sent %s to %s' % (filename, idurl))
            #TODO request.getPeer()
#             transport_control.sendStatusReport(
#                 request.getClient(),
#                 filename,
#                 'finished',
#                 'http',)
        _Outbox.pop(idurl, None)
        return r

#------------------------------------------------------------------------------

class TransportHTTPClientFactory(HTTPClientFactory):
    pass

class TransportHTTPProxyClientFactory(HTTPClientFactory):
    def setURL(self, url):
        HTTPClientFactory.setURL(self, url)
        self.path = url

#------------------------------------------------------------------------------

class Receiver(object):

    def loop(self):
        global _ReceivingLoop
        global _Contacts
        global _ToIncreaseDelay
        global _LastPingTimeDict
        global _PingDelayDict
        global _ConnectionsDict
        global _CurrentDelay
        lg.out(6, 'http_node.Receiver.loop')
        # _CurrentDelay = settings.getHTTPDelay()
        for idurl, hostport in _Contacts.items():
            if idurl in _ConnectionsDict:
                continue
            lasttm = _LastPingTimeDict.get(idurl, 0)
            delay = _PingDelayDict.get(idurl, _CurrentDelay)
            dt = time.time() - lasttm
            if dt < delay:
                continue
            _ConnectionsDict[idurl] = self.do_ping(idurl, hostport[0], hostport[1])
            _LastPingTimeDict[idurl] = time.time()
        _ReceivingLoop = reactor.callLater(1, self.loop)
        return _ReceivingLoop

    def on_ping_success(self, src, idurl, host, port, conn):
        global _LastPingTimeDict
        global _ConnectionsDict
        if len(src) == 0:
            increase_receiving_delay(idurl)
        else:
            parts = src.splitlines()
            lg.out(14, 'http_node.receive.success %d bytes in %d parts from %s (%s:%s)' % (len(src), len(parts), idurl, host, port))
            for part64 in parts:
                try:
                    part = base64.b64decode(part64.strip())
                except:
                    lg.out(14, 'http_node.receive.success ERROR in base64.b64decode()')
                    decrease_receiving_delay(idurl)
                    continue
                fd, filename = tmpfile.make("http-in", extension='.http')
                os.write(fd, part)
                os.close(fd)
                decrease_receiving_delay(idurl)
#                 transport_control.receiveStatusReport(
#                     filename,
#                     'finished',
#                     'http',
#                     host+':'+port,)
#             transport_control.log('http', 'finish connection with %s:%s ' % (host, port))
        conn.disconnect()
        # TODO: keep it opened!
        _ConnectionsDict.pop(idurl, None)

    def on_ping_failed(self, x, idurl, host, port, conn):
        global _LastPingTimeDict
        global _ConnectionsDict
        increase_receiving_delay(idurl)
        conn.disconnect()
        _ConnectionsDict.pop(idurl, None)

    def do_ping(self, idurl, host, port):
        lg.out(14, 'http_node.receive.ping     %s (%s:%s)' % (idurl, host, port))
        url = b'http://' + host + b':' + strng.to_bin(str(port))

        if net_misc.proxy_is_on():
            f = TransportHTTPProxyClientFactory(url, method='POST', headers={
                'User-Agent': 'DataHaven.NET transport_http', 'idurl': my_id.getLocalID(), } )
            conn = reactor.connectTCP(net_misc.get_proxy_host(), int(net_misc.get_proxy_port()), f)
        else:
            f = TransportHTTPClientFactory(url, method='POST', headers={
                'User-Agent': 'DataHaven.NET transport_http', 'idurl': my_id.getLocalID(), } )
            conn = reactor.connectTCP(host, int(port), f)

        f.deferred.addCallback(self.on_ping_success, idurl, host, port, conn)
        f.deferred.addErrback(self.on_ping_failed, idurl, host, port, conn)
        return conn

#------------------------------------------------------------------------------

def decrease_receiving_delay(idurl):
    global _PingDelayDict
    global _CurrentDelay
    lg.out(14, 'http_node.decrease_receiving_delay ' + idurl)
    _PingDelayDict[idurl] = _CurrentDelay

def increase_receiving_delay(idurl):
    global _PingDelayDict
    global _CurrentDelay
    if idurl not in _PingDelayDict:
        _PingDelayDict[idurl] = _CurrentDelay
    d = _PingDelayDict[idurl]
    if d < settings.DefaultSendTimeOutHTTP() / 2:
        lg.out(14, 'http_node.increase_receiving_delay   %s for %s' % (str(d), idurl))
        _PingDelayDict[idurl] *= 2

#------------------------------------------------------------------------------

def start_receiving():
    global _Receiver
    if _Receiver is not None:
        lg.warn('already started')
        return _Receiver
    _Receiver = Receiver()
    _Receiver.loop()
    return _Receiver


def stop_receiving():
    global _ReceivingLoop
    lg.out(6, 'http_node.stop_receiving')
    if _ReceivingLoop is None:
        lg.out(8, 'http_node.stop_receiving _ReceivingLoop is None')
        return
    if _ReceivingLoop.called:
        lg.out(8, 'http_node.stop_receiving _ReceivingLoop is already called')
        return
    _ReceivingLoop.cancel()
    del _ReceivingLoop
    _ReceivingLoop = None

#------------------------------------------------------------------------------

def push_contact(idurl):
    global _Contacts
    global _PingDelayDict
    global _CurrentDelay
    ident = identitycache.FromCache(idurl)
    if ident is None:
        lg.err('"%s" not in the cache' % idurl)
        return None
    http_contact = ident.getProtoContact('http')
    if http_contact is None:
        if _Debug:
            lg.out(_DebugLevel * 2, 'http_node.add_contact SKIP "%s" : no http contacts found in identity' % idurl)
        return None
    _, host, port, _ = nameurl.UrlParse(http_contact)
    new_item = False
    if idurl in _Contacts:
        new_item = True
    _Contacts[idurl] = (host, port)
    _PingDelayDict[idurl] = _CurrentDelay
    if new_item:
        if _Debug:
            lg.out(_DebugLevel, 'http_node.add_contact ADDED "%s" on %s:%s' % (idurl, host, port))
    else:
        if _Debug:
            lg.out(_DebugLevel, 'http_node.add_contact UPDATED "%s" on %s:%s' % (idurl, host, port))
    return idurl

#------------------------------------------------------------------------------

def do_update_contacts():
    global _Contacts
    if _Debug:
        lg.out(_DebugLevel, 'http_node.update_contacts')
    _Contacts.clear()

    for idurl in contactsdb.contacts(include_all=True):
        lg.out(10, 'http_node.update_contacts want ' + idurl)
        if idurl == my_id.getLocalID():
            continue
        latest_identity = identitycache.GetLatest(idurl)
        if isinstance(latest_identity, Deferred):
            latest_identity.addCallback(lambda src: push_contact(idurl))
            latest_identity.addErrback(lambda err: lg.out(
                _DebugLevel, 'http_node.update_contacts "%s" failed to cache' % idurl) if _Debug else None)
        else:
            push_contact(idurl)

#------------------------------------------------------------------------------

def on_contacts_changed(oldlist, newlist):
    do_update_contacts()

#------------------------------------------------------------------------------

def usage():
    print('''usage:
http_node.py send [server_port] [to idurl] [filename]
http_node.py receive
''')

def main():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    from twisted.internet.defer import setDebugging
    setDebugging(True)
    # from twisted.python import log as twisted_log
    # twisted_log.startLogging(sys.stdout)
    lg.set_debug_level(20)
    settings.init()
    settings.update_proxy_settings()

    if sys.argv.count('receive'):
        start_receiving()
#         global _Contacts
#         _Contacts['http://p2p-id.ru/veselin.xml'] = ('127.0.0.1', 9122)

    elif sys.argv.count('send'):
        start_sending(port=int(sys.argv[2]))
        send_file(sys.argv[3], sys.argv[4])

    else:
        usage()
        return

    reactor.run()

#------------------------------------------------------------------------------


if __name__ == '__main__':
    main()
