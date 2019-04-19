#!/usr/bin/env python
# id_registrator.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (id_registrator.py) is part of BitDust Software.
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
.. module:: id_registrator.

.. role:: red


Creates new identities to be able to access BitDust network.
Another node in the network can start ID server and store a copy of your identity.
Then third node can access that ID server and download your identity.

Normally, software will do all stuff for you and just pick few random ID servers,
ping them and register your identity.

But you can decide which ID servers you prefer and modify your "known" ID servers:

    bitdust set services/identity-propagate/known-servers first-server.com:80:6661,second-host.net:8080:6661


Your global IDURL is formed based on your nickname and DNS name (or IP address) of the first ID server.

If one of your ID servers is down, you can find a fresh one and "propagate" your identity there
and then remove dead ID server from the list of your sources: "identity migration" (not implemented yet).
This process will be automated and network identification will become much more reliable.

To be able to test locally you can start your own local ID server:

    bitdust set services/identity-server/host localhost
    ~/.bitdust/venv/bin/python userid/id_server.py 8080 6661


Modify your "known" ID servers:

    bitdust set services/identity-propagate/known-servers localhost:8080:6661


Modify your settings to use only one ID server:

    bitdust set services/identity-propagate/min-servers 1
    bitdust set services/identity-propagate/max-servers 1


Then you can create a "local" identity:

    ~/.bitdust/venv/bin/python userid/id_registrator.py my_nickname_here localhost


EVENTS:
    * :red:`id-exist`
    * :red:`id-not-exist`
    * :red:`id-server-failed`
    * :red:`id-server-response`
    * :red:`local-ip-detected`
    * :red:`my-id-exist`
    * :red:`my-id-failed`
    * :red:`my-id-sent`
    * :red:`start`
    * :red:`stun-failed`
    * :red:`stun-success`
    * :red:`timer-15sec`
    * :red:`timer-2min`
    * :red:`timer-30sec`
    * :red:`timer-5sec`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import sys
import random

from twisted.internet.defer import DeferredList
from six.moves import range

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from system import bpio

from lib import nameurl
from lib import net_misc
from lib import misc
from lib import strng

from main import settings
from main import config

from stun import stun_client

from crypt import key

from userid import my_id
from userid import identity
from userid import known_servers

#------------------------------------------------------------------------------

_IdRegistrator = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _IdRegistrator
    if _IdRegistrator is None:
        # set automat name and starting state here
        _IdRegistrator = IdRegistrator(
            name='id_registrator',
            state='AT_STARTUP',
            debug_level=2,
            log_transitions=True,
            log_events=True,
            publish_events=True,
        )
    if event is not None:
        _IdRegistrator.automat(event, *args, **kwargs)
    return _IdRegistrator


class IdRegistrator(automat.Automat):
    """
    This class implements all the functionality of the ``id_registrator()``
    state machine.
    """

    timers = {
        'timer-2min': (120, ['SEND_ID']),
        'timer-30sec': (30.0, ['NAME_FREE?']),
        'timer-5sec': (5.0, ['REQUEST_ID']),
        'timer-15sec': (15.0, ['REQUEST_ID']),
    }

    MESSAGES = {
        'MSG_0': ['ping identity servers...'],
        'MSG_1': ['checking the availability of a user name'],
        'MSG_2': ['checking network configuration'],
        'MSG_3': ['detecting external IP...'],
        'MSG_4': ['registering on ID servers...'],
        'MSG_5': ['verifying my identity'],
        'MSG_6': ['new user %(login)s registered successfully!', 'green'],
        'MSG_7': ['ID servers not responding', 'red'],
        'MSG_8': ['name %(login)s already taken', 'red'],
        'MSG_9': ['network connection error', 'red'],
        'MSG_10': ['connection error while sending my identity', 'red'],
        'MSG_11': ['identity verification failed', 'red'],
        'MSG_12': ['time out requesting from identity servers', 'red'],
        'MSG_13': ['time out sending to identity servers', 'red'],
        'MSG_14': ['generating your Private Key'],
    }

    def msg(self, msgid, *args, **kwargs):
        msg = self.MESSAGES.get(msgid, ['', 'black'])
        text = msg[0] % {
            'login': strng.to_text(bpio.ReadTextFile(settings.UserNameFilename())),
            'externalip': strng.to_text(misc.readExternalIP()),
            'localip': strng.to_text(bpio.ReadTextFile(settings.LocalIPFilename())),
        }
        color = 'black'
        if len(msg) == 2:
            color = msg[1]
        return text, color

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.known_servers = {}  # host : (web port, tcp port)
        self.preferred_servers = []
        self.min_servers = 1
        self.max_servers = 10
        self.discovered_servers = []
        self.good_servers = []
        self.registrations = []
        self.free_idurls = []
        self.new_identity = None
        self.last_message = ''

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when automat's state were
        changed.
        """
        from main import installer
        installer.A('id_registrator.state', newstate)

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start':
                self.state = 'ID_SERVERS?'
                self.doSaveMyName(*args, **kwargs)
                self.doSelectRandomServers(*args, **kwargs)
                self.doPingServers(*args, **kwargs)
                self.doPrint(self.msg('MSG_0', *args, **kwargs))
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---ID_SERVERS?---
        elif self.state == 'ID_SERVERS?':
            if (event == 'id-server-response' or event == 'id-server-failed') and self.isAllTested(*args, **kwargs) and self.isSomeAlive(*args, **kwargs):
                self.state = 'NAME_FREE?'
                self.doRequestServers(*args, **kwargs)
                self.doPrint(self.msg('MSG_1', *args, **kwargs))
            elif (event == 'id-server-response' or event == 'id-server-failed') and self.isAllTested(*args, **kwargs) and not self.isSomeAlive(*args, **kwargs):
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_7', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
        #---NAME_FREE?---
        elif self.state == 'NAME_FREE?':
            if event == 'id-not-exist' and self.isAllResponded(*args, **kwargs) and self.isFreeIDURLs(*args, **kwargs):
                self.state = 'LOCAL_IP'
                self.doDetectLocalIP(*args, **kwargs)
                self.doPrint(self.msg('MSG_2', *args, **kwargs))
            elif event == 'timer-30sec' or (event == 'id-exist' and self.isAllResponded(*args, **kwargs) and not self.isFreeIDURLs(*args, **kwargs)):
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_8', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
        #---LOCAL_IP---
        elif self.state == 'LOCAL_IP':
            if event == 'local-ip-detected':
                self.state = 'EXTERNAL_IP'
                self.doStunExternalIP(*args, **kwargs)
                self.doPrint(self.msg('MSG_3', *args, **kwargs))
        #---EXTERNAL_IP---
        elif self.state == 'EXTERNAL_IP':
            if event == 'stun-success':
                self.state = 'SEND_ID'
                self.doPrint(self.msg('MSG_14', *args, **kwargs))
                self.doCreateMyIdentity(*args, **kwargs)
                self.doPrint(self.msg('MSG_4', *args, **kwargs))
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'stun-failed':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_9', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
        #---SEND_ID---
        elif self.state == 'SEND_ID':
            if event == 'my-id-sent':
                self.state = 'REQUEST_ID'
                self.doRequestMyIdentity(*args, **kwargs)
                self.doPrint(self.msg('MSG_5', *args, **kwargs))
            elif event == 'my-id-failed':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_10', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-2min':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_13', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
        #---REQUEST_ID---
        elif self.state == 'REQUEST_ID':
            if event == 'my-id-exist' and self.isMyIdentityValid(*args, **kwargs):
                self.state = 'DONE'
                self.doSaveMyIdentity(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
                self.doPrint(self.msg('MSG_6', *args, **kwargs))
            elif event == 'timer-5sec':
                self.doRequestMyIdentity(*args, **kwargs)
            elif event == 'my-id-exist' and not self.isMyIdentityValid(*args, **kwargs):
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_11', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
            elif event == 'timer-15sec':
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_12', *args, **kwargs))
                self.doDestroyMe(*args, **kwargs)
        return None

    def isMyIdentityValid(self, *args, **kwargs):
        """
        Condition method.
        """
        id_from_server = identity.identity(xmlsrc=args[0])
        if not id_from_server.isCorrect():
            lg.warn('my identity is not correct')
            return False
        if not id_from_server.Valid():
            lg.warn('my identity is not valid')
            return False
        if self.new_identity.serialize() != id_from_server.serialize():
            # TODO: seems an issue here!
            lg.warn('my identity source is different than copy received from id server')
            return False
        return True

    def isSomeAlive(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.good_servers) > 0

    def isAllResponded(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.registrations) == 0

    def isAllTested(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.discovered_servers) == 0

    def isFreeIDURLs(self, *args, **kwargs):
        """
        Condition method.
        """
        return len(self.free_idurls) > 0

    def doSaveMyName(self, *args, **kwargs):
        """
        Action method.
        """
        if args:
            login = args[0]['username']
            preferred_servers = args[0].get('preferred_servers', [])
        else:
            login = kwargs['username']
            preferred_servers = kwargs.get('preferred_servers', [])
        self.preferred_servers = [s.strip() for s in preferred_servers]
        if not self.known_servers:
            self.known_servers = known_servers.by_host()
        if not self.preferred_servers:
            try:
                for srv in str(config.conf().getData('services/identity-propagate/preferred-servers')).split(','):
                    if srv.strip():
                        self.preferred_servers.append(srv.strip())
            except:
                pass
        self.min_servers = max(
            settings.MinimumIdentitySources(),
            config.conf().getInt('services/identity-propagate/min-servers') or settings.MinimumIdentitySources())
        self.max_servers = min(
            settings.MaximumIdentitySources(),
            config.conf().getInt('services/identity-propagate/max-servers') or settings.MaximumIdentitySources())
        lg.out(4, 'id_registrator.doSaveMyName [%s]' % login)
        lg.out(4, '    known_servers=%s' % self.known_servers)
        lg.out(4, '    preferred_servers=%s' % self.preferred_servers)
        lg.out(4, '    min_servers=%s' % self.min_servers)
        lg.out(4, '    max_servers=%s' % self.max_servers)
        bpio.WriteTextFile(settings.UserNameFilename(), login)

    def doSelectRandomServers(self, *args, **kwargs):
        """
        Action method.
        TODO: we also can search available id servers in DHT network as well
        """
        if self.preferred_servers:
            self.discovered_servers.extend(self.preferred_servers)
        num_servers = random.randint(self.min_servers, self.max_servers)
        needed_servers = num_servers - len(self.discovered_servers)
        for _ in range(needed_servers):
            # take a list of all known servers (only host names)
            s = set(self.known_servers.keys())
            # exclude already discovered servers
            s.difference_update(self.discovered_servers)
            if len(s) > 0:
                # if found some known servers - just pick a randome one
                self.discovered_servers.append(random.choice(list(s)))
        lg.out(4, 'id_registrator.doSelectRandomServers %s' % str(self.discovered_servers))

    def doPingServers(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(4, 'id_registrator.doPingServers    %d in list' % len(self.discovered_servers))

        def _cb(htmlsrc, id_server_host):
            lg.out(4, '            RESPONDED: %s' % id_server_host)
            if self.preferred_servers and id_server_host in self.preferred_servers:
                self.good_servers.insert(0, id_server_host)
            else:
                self.good_servers.append(id_server_host)
            self.discovered_servers.remove(id_server_host)
            self.automat('id-server-response', (id_server_host, htmlsrc))

        def _eb(err, id_server_host):
            lg.out(4, '               FAILED: %s : %s' % (id_server_host, err))
            self.discovered_servers.remove(id_server_host)
            self.automat('id-server-failed', (id_server_host, err))

        for host in self.discovered_servers:
            webport, tcpport = known_servers.by_host().get(
                host,
                (settings.IdentityWebPort(), settings.IdentityServerPort()),
            )
            if webport == 80:
                webport = ''
            server_url = nameurl.UrlMake('http', strng.to_text(host), webport, '')
            lg.out(4, '               connecting to %s:%s   known tcp port is %d' % (
                server_url, webport, tcpport, ))
            d = net_misc.getPageTwisted(server_url, timeout=10)
            d.addCallback(_cb, host)
            d.addErrback(_eb, host)

    def doRequestServers(self, *args, **kwargs):
        """
        Action method.
        """
        login = bpio.ReadTextFile(settings.UserNameFilename())

        def _cb(xmlsrc, idurl, host):
            if not xmlsrc:
                if self.preferred_servers and host in self.preferred_servers:
                    self.free_idurls.insert(0, idurl)
                else:
                    self.free_idurls.append(idurl)
                self.registrations.remove(idurl)
                self.automat('id-not-exist', idurl)
            else:
                lg.out(4, '                EXIST: %s' % idurl)
                self.registrations.remove(idurl)
                self.automat('id-exist', idurl)

        def _eb(err, idurl, host):
            lg.out(4, '            NOT EXIST: %s' % idurl)
            if self.preferred_servers and host in self.preferred_servers:
                self.free_idurls.insert(0, idurl)
            else:
                self.free_idurls.append(idurl)
            self.registrations.remove(idurl)
            self.automat('id-not-exist', idurl)

        for host in self.good_servers:
            webport, tcpport = known_servers.by_host().get(
                host, (settings.IdentityWebPort(), settings.IdentityServerPort()))
            if webport == 80:
                webport = ''
            idurl = nameurl.UrlMake('http', strng.to_text(host), webport, login + '.xml')
            lg.out(4, '    %s' % idurl)
            d = net_misc.getPageTwisted(idurl, timeout=10)
            d.addCallback(_cb, idurl, host)
            d.addErrback(_eb, idurl, host)
            self.registrations.append(idurl)
        lg.out(4, 'id_registrator.doRequestServers login=%s registrations=%d' % (login, len(self.registrations)))

    def doDetectLocalIP(self, *args, **kwargs):
        """
        Action method.
        """
        localip = net_misc.getLocalIp()
        bpio.WriteTextFile(settings.LocalIPFilename(), localip)
        lg.out(4, 'id_registrator.doDetectLocalIP [%s]' % localip)
        self.automat('local-ip-detected')

    def doStunExternalIP(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(4, 'id_registrator.doStunExternalIP')
        if len(self.free_idurls) == 1:
            if self.free_idurls[0].count(b'localhost:') or self.free_idurls[0].count(b'127.0.0.1:'):
                # if you wish to create a local identity you do not need to stun external IP at all
                self.automat('stun-success', '127.0.0.1')
                return True

        def save(result):
            lg.out(4, '            external IP : %s' % result)
            if result['result'] != 'stun-success':
                self.automat('stun-failed')
                return
            ip = result['ip']
            bpio.WriteTextFile(settings.ExternalIPFilename(), ip)
            self.automat('stun-success', ip)

        rnd_udp_port = random.randint(
            settings.DefaultUDPPort(),
            settings.DefaultUDPPort() + 500,
        )
        rnd_dht_port = random.randint(
            settings.DefaultDHTPort(),
            settings.DefaultDHTPort() + 500,
        )
        d = stun_client.safe_stun(udp_port=rnd_udp_port, dht_port=rnd_dht_port)
        d.addCallback(save)
        d.addErrback(lambda _: self.automat('stun-failed'))
        return True

    def doCreateMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self._create_new_identity()

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        # TODO: just to debug - skip sending to ID servers and go further
        # self.state = 'REQUEST_ID'
        # self.event('my-id-exist', self.new_identity.serialize())
        # return
        mycurrentidentity = None
        if my_id.isLocalIdentityReady():
            mycurrentidentity = my_id.getLocalIdentity()
        my_id.setLocalIdentity(self.new_identity)

        def _cb(x):
            my_id.setLocalIdentity(mycurrentidentity)
            self.automat('my-id-sent')

        def _eb(x):
            my_id.setLocalIdentity(mycurrentidentity)
            self.automat('my-id-failed')

        dl = self._send_new_identity()
        dl.addCallback(_cb)
        dl.addErrback(_eb)

    def doRequestMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(8, 'id_registrator.doRequestMyIdentity')

        def _cb(src):
            self.automat('my-id-exist', src)

        def _eb(err):
            self.automat('my-id-not-exist', err)

        for idurl in self.new_identity.sources:
            lg.out(8, '        %s' % idurl)
            d = net_misc.getPageTwisted(idurl, timeout=20)
            d.addCallback(_cb)
            d.addErrback(_eb)

    def doSaveMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(4, 'id_registrator.doSaveMyIdentity %s' % self.new_identity)
        my_id.setLocalIdentity(self.new_identity)
        my_id.saveLocalIdentity()

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.executeStateChangedCallbacks(oldstate=None, newstate=self.state, event_string=None, args=args)
        self.destroy(dead_state=self.state)
        global _IdRegistrator
        _IdRegistrator = None

    def doPrint(self, *args, **kwargs):
        """
        Action method.
        """
        from main import installer
        installer.A().event('print', *args, **kwargs)
        self.last_message = args[0][0]
        lg.out(6, 'id_registrator.doPrint: %s' % str(*args, **kwargs))

    def _create_new_identity(self):
        """
        Generate new Private key and new identity file.
        Reads some extra info from config files.
        """
        login = strng.to_bin(bpio.ReadTextFile(settings.UserNameFilename()))
        externalIP = strng.to_bin(misc.readExternalIP()) or b'127.0.0.1'
        if self.free_idurls[0].count(b'127.0.0.1'):
            externalIP = b'127.0.0.1'
        lg.out(4, 'id_registrator._create_new_identity %s %s ' % (login, externalIP))
        key.InitMyKey()
        if not key.isMyKeyReady():
            key.GenerateNewKey()
        lg.out(4, '    my key is ready')
        ident = my_id.buildDefaultIdentity(
            name=login, ip=externalIP, idurls=self.free_idurls)
        # my_id.rebuildLocalIdentity(
        #     identity_object=ident, revision_up=True, save_identity=False)
        # localIP = bpio.ReadTextFile(settings.LocalIPFilename())
        my_identity_xmlsrc = ident.serialize(as_text=True)
        newfilename = settings.LocalIdentityFilename() + '.new'
        bpio.WriteTextFile(newfilename, my_identity_xmlsrc)
        self.new_identity = ident
        lg.out(4, '    wrote %d bytes to %s' % (len(my_identity_xmlsrc), newfilename))

    def _send_new_identity(self):
        """
        Send created identity to the identity server to register it.
        TODO: need to close transport and gateway after that
        """
        lg.out(4, 'id_registrator._send_new_identity ')
        from transport import gateway
        from transport import network_transport
        from transport.tcp import tcp_interface
        gateway.init()
        interface = tcp_interface.GateInterface()
        transport = network_transport.NetworkTransport('tcp', interface)
        transport.automat('init', gateway.listener())
        transport.automat('start')
        gateway.start()
        sendfilename = settings.LocalIdentityFilename() + '.new'
        dlist = []
        for idurl in self.new_identity.sources:
            self.free_idurls.remove(strng.to_bin(idurl))
            _, host, _, _ = nameurl.UrlParse(idurl)
            _, tcpport = known_servers.by_host().get(
                host, (settings.IdentityWebPort(), settings.IdentityServerPort()))
            srvhost = net_misc.pack_address((host, tcpport, ))
            dlist.append(gateway.send_file_single(idurl, 'tcp', srvhost, sendfilename, 'Identity'))
        # assert len(self.free_idurls) == 0
        return DeferredList(dlist, fireOnOneCallback=True)

#------------------------------------------------------------------------------


def main():
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    from twisted.internet import reactor  # @UnresolvedImport
    if len(sys.argv) > 2:
        args = (sys.argv[1], sys.argv[2])
    else:
        args = (sys.argv[1])
    A().addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='DONE')  # @UndefinedVariable
    A().addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='FAILED')  # @UndefinedVariable
    reactor.callWhenRunning(A, 'start', args)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------


if __name__ == "__main__":
    main()
