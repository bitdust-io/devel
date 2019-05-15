#!/usr/bin/env python
# id_rotator.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (id_rotator.py) is part of BitDust Software.
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


"""
.. module:: id_rotator
.. role:: red

.. raw:: html

    <a href="https://bitdust.io/wiki/p2p/id_rotator.png" target="_blank">
    <img src="https://bitdust.io/wiki/p2p/id_rotator.png" style="max-width:100%;">
    </a>


BitDust id_rotator() Automat

EVENTS:
    * :red:`check`
    * :red:`found-new-id-source`
    * :red:`id-server-failed`
    * :red:`my-id-exist`
    * :red:`my-id-failed`
    * :red:`my-id-sent`
    * :red:`my-id-updated`
    * :red:`no-id-servers-found`
    * :red:`ping-done`
    * :red:`ping-failed`
    * :red:`run`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 12

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys as _s, os.path as _p
    _s.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(_s.argv[0])), '..')))

#------------------------------------------------------------------------------

import random

from twisted.internet.defer import Deferred, DeferredList  # @UnresolvedImport

#------------------------------------------------------------------------------

from logs import lg

from automats import automat

from lib import net_misc
from lib import nameurl
from lib import strng

from main import config
from main import settings

from userid import identity
from userid import my_id
from userid import known_servers

#------------------------------------------------------------------------------

_IdRotator = None

#------------------------------------------------------------------------------

def check():
    """
    Returns True/False via deferred object to report situation with my identity sources.
    """
    result_defer = Deferred()
    ir = IdRotator()
    ir.automat('check', result_defer=result_defer)
    return result_defer


def run(preferred_servers={}):
    """
    Executes id_rotator() automat to check my identity sources and if republish my identity
    on another ID server if current situation "is not healthy".
    Input parameter "preferred_servers" can be used to control which servers to be used
    when replacing a dead one.
    Returns True/False via deferred object to report result.
    """
    result_defer = Deferred()
    ir = IdRotator()
    ir.automat('run', result_defer=result_defer, preferred_servers=preferred_servers)
    return result_defer

#------------------------------------------------------------------------------

class IdRotator(automat.Automat):
    """
    This class implements all the functionality of ``id_rotator()`` state machine.
    """

    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=False, **kwargs):
        """
        Builds `id_rotator()` state machine.
        """
        super(IdRotator, self).__init__(
            name="id_rotator",
            state="AT_STARTUP",
            debug_level=debug_level,
            log_events=log_events,
            log_transitions=log_transitions,
            publish_events=publish_events,
            **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `id_rotator()` machine.
        """

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `id_rotator()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `id_rotator()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'run' or event == 'check':
                self.state = 'ID_SERVERS?'
                self.doInit(event, *args, **kwargs)
                self.doPingMyIDServers(*args, **kwargs)
        #---ID_SERVERS?---
        elif self.state == 'ID_SERVERS?':
            if event == 'ping-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ping-done' and ( self.isChecking(*args, **kwargs) or self.isHealthy(*args, **kwargs) ):
                self.state = 'DONE'
                self.doReportDone(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ping-done' and not self.isChecking(*args, **kwargs) and not self.isHealthy(*args, **kwargs):
                self.state = 'NEW_SOURCE!'
                self.doSelectNewIDServer(*args, **kwargs)
        #---NEW_SOURCE!---
        elif self.state == 'NEW_SOURCE!':
            if event == 'no-id-servers-found':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'found-new-id-source':
                self.state = 'MY_ID_ROTATE'
                self.doRebuildMyIdentity(*args, **kwargs)
        #---MY_ID_ROTATE---
        elif self.state == 'MY_ID_ROTATE':
            if event == 'my-id-updated':
                self.state = 'SEND_ID'
                self.doSendMyIdentity(*args, **kwargs)
        #---SEND_ID---
        elif self.state == 'SEND_ID':
            if event == 'my-id-sent':
                self.state = 'REQUEST_ID'
                self.doRequestMyIdentity(*args, **kwargs)
            elif event == 'my-id-failed':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---REQUEST_ID---
        elif self.state == 'REQUEST_ID':
            if event == 'my-id-exist' and self.isMyIdentityValid(*args, **kwargs):
                self.state = 'DONE'
                self.doReportDone(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'id-server-failed' or ( event == 'my-id-exist' and not self.isMyIdentityValid(*args, **kwargs) ):
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isHealthy(self, *args, **kwargs):
        """
        Condition method.
        """
        return self._is_healthy(args[0])

    def isChecking(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.check_only

    def isMyIdentityValid(self, *args, **kwargs):
        """
        Condition method.
        """
        # TODO: check all results here
        return True

    def doInit(self, event, *args, **kwargs):
        """
        Action method.
        """
        self.result_defer = kwargs.get('result_defer')
        self.check_only = False
        if event == 'check':
            self.check_only = True
        self.alive_idurls = []
        self.known_servers = known_servers.by_host()
        self.preferred_servers = kwargs.get('preferred_servers', {})
        if not self.preferred_servers:
            try:
                for srv in str(config.conf().getData('services/identity-propagate/preferred-servers')).split(','):
                    if srv.strip():
                        host, web_port, tcp_port = srv.strip().split(':')
                        self.preferred_servers[host] = (web_port, tcp_port, )
            except:
                pass
        self.current_servers = []
        for idurl in my_id.getLocalIdentity().getSources():
            self.current_servers.append(nameurl.GetHost(idurl))
        if _Debug:
            lg.args(_DebugLevel, known_servers=self.known_servers, preferred_servers=self.preferred_servers)

    def doPingMyIDServers(self, *args, **kwargs):
        """
        Action method.
        """
        my_sources = my_id.getLocalIdentity().getSources()
        dl = []
        for idurl in my_sources:
            d = net_misc.getPageTwisted(idurl, timeout=5)
            dl.append(d)
        d = DeferredList(dl, consumeErrors=True)
        d.addCallback(self._do_check_ping_results)
        d.addErrback(lambda err: self.automat('ping-failed', err))

    def doSelectNewIDServer(self, *args, **kwargs):
        """
        Action method.
        """
        target_servers = self.preferred_servers
        if not target_servers:
            target_servers = self.known_servers
        # make sure to not choose a server I already have in my ID sources
        for current_server in self.current_servers:
            if current_server in target_servers:
                target_servers.remove(current_server)

        if not target_servers:
            self.automat('no-id-servers-found')
            return

        target_hosts = list(target_servers.keys())
        random.shuffle(target_hosts)
        if _Debug:
            lg.args(_DebugLevel, target_hosts=target_hosts)

        def _new_idurl_exist(idsrc, new_idurl, pos):
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._new_idurl_exist %r already with same name' % new_idurl)
            if pos + 1 >= len(target_hosts):
                self.automat('no-id-servers-found')
            else:
                _ping_one_server(pos + 1)

        def _new_idurl_not_exist(err, new_idurl):
            lg.info('found new identity source available to use: %r' % new_idurl)
            self.automat('found-new-id-source', new_idurl)

        def _server_replied(htmlsrc, host, pos):
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._server_replied %r' % host)
            webport, _ = target_servers[host]
            if webport == 80:
                webport = ''
            new_idurl = nameurl.UrlMake('http', strng.to_text(host), webport, my_id.getIDName() + '.xml')
            d = net_misc.getPageTwisted(new_idurl, timeout=10)
            d.addCallback(_new_idurl_exist, new_idurl, pos)
            d.addErrback(_new_idurl_not_exist, new_idurl)

        def _server_failed(err, host, pos):
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._server_failed %r with %r' % (host, err))
            if pos + 1 >= len(target_hosts):
                self.automat('no-id-servers-found')
            else:
                _ping_one_server(pos + 1)

        def _ping_one_server(pos):
            host = target_hosts[pos]
            webport, tcpport = target_servers[host]
            if webport == 80:
                webport = ''
            server_url = nameurl.UrlMake('http', strng.to_text(host), webport, '')
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._ping_one_server at %s:%s known tcp port is %d' % (
                    server_url, webport, tcpport, ))
            d = net_misc.getPageTwisted(server_url, timeout=10)
            d.addCallback(_server_replied, host, pos)
            d.addErrback(_server_failed, host, pos)
        
        _ping_one_server(0)

    def doRebuildMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        current_sources = my_id.getLocalIdentity().getSources()
        new_sources = []
        # first get rid of "dead" sources
        for current_idurl in current_sources:
            if current_idurl not in self.alive_idurls:
                continue
            new_sources.append(current_idurl)
        # and add new "good" source to the end of the list
        new_sources.append(args[0])
        if _Debug:
            lg.args(_DebugLevel, current_sources=current_sources, alive_idurls=self.alive_idurls, new_sources=new_sources)
        my_id.rebuildLocalIdentity(new_sources=new_sources)
        self.automat('my-id-updated')

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        d = self._do_send_my_identity()
        d.addCallback(lambda results: self.automat('my-id-sent', results))
        d.addErrback(lambda err: self.automat('my-id-failed', err))

    def doRequestMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        if _Debug:
            lg.out(_DebugLevel, 'id_rotator.doRequestMyIdentity')

        def _cb(results):
            # TODO: validate my identity in all responses
            self.automat('my-id-exist', results)

        def _eb(err):
            self.automat('my-id-not-exist', err)

        dl = []
        for idurl in my_id.getLocalIdentity().getSources():
            dl.append(net_misc.getPageTwisted(idurl, timeout=10))
        d = DeferredList(dl)
        d.addCallback(_cb)
        d.addErrback(_eb)

    def doReportDone(self, event, *args, **kwargs):
        """
        Action method.
        """
        if not self.result_defer:
            return
        if event == 'ping-done':
            self.result_defer.callback(self._is_healthy(args[0]))
        elif event == 'my-id-exists':
            self.result_defer.callback(True)

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('id_rotator finished with failed result %r : %r' % (event, args[0]))
        if not self.result_defer:
            return
        self.result_defer.errback(args[0])

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.check_only = None
        self.result_defer = None
        self.alive_idurls = None
        self.current_servers = None
        self.preferred_servers = None
        self.known_servers = None
        self.destroy()

    def _is_healthy(self, ping_results):
        # TODO: for now simply check that first identity server in my identity is alive
        # we can implement more "aggressive" checks later...
        # for example if any of my sources is not alive -> replace him also
        # also we can check here if I have enough sources according to those configs:
        #     services/identity-propagate/min-servers
        #     services/identity-propagate/max-servers
        return bool(ping_results[0])

    def _do_check_ping_results(self, ping_results):
        self.alive_idurls = []
        my_sources = my_id.getLocalIdentity().getSources()
        latest_revision = -1
        pos = -1
        for result, remote_identity_src in ping_results:
            pos += 1
            idurl = my_sources[pos]
            if not result:
                self.alive_idurls.append(None)
                continue
            try:
                remote_ident = identity.identity(xmlsrc=remote_identity_src)
                if not remote_ident.isCorrect():
                    raise Exception('remote identity not correct at position %r' % pos)
                if not remote_ident.Valid():
                    raise Exception('remote identity not valid at position %r' % pos)
                if latest_revision == -1:
                    latest_revision = remote_ident.getRevisionValue()
                if latest_revision != remote_ident.getRevisionValue():
                    raise Exception('remote identity have wrong revision at position %r' % pos)
                # TODO: need to also check here that all ID servers are storing same identity
            except:
                lg.exc()
                self.alive_idurls.append(None)
                continue
            self.alive_idurls.append(idurl)
        if _Debug:
            lg.args(_DebugLevel, self.alive_idurls)
        if not self.alive_idurls or not list(filter(None, self.alive_idurls)):
            # if no alive servers found then probably network is down
            # and we should not do anything at the moment
            # TODO: but we can also check in that case if another ID "well known" server is alive
            # otherwise we can get situation when all my id servers are down and id_rotator do nothing to fix that
            self.automat('ping-failed', [])
            return
        self.automat('ping-done', self.alive_idurls)

    def _do_send_my_identity(self):
        """
        Send my updated identity to the identity servers to register it.
        """
        if _Debug:
            lg.out(_DebugLevel, 'id_rotator._do_send_my_identity')
        from transport.tcp import tcp_node
        sendfilename = settings.LocalIdentityFilename() + '.new'
        dlist = []
        for idurl in my_id.getLocalIdentity().getSources():
            _, host, _, _ = nameurl.UrlParse(idurl)
            tcpport = None
            if host in self.preferred_servers:
                tcpport = self.preferred_servers[host][1]
            if not tcpport and host in self.known_servers:
                tcpport = self.known_servers[host][1]
            if not tcpport:
                tcpport = settings.IdentityServerPort()
            srvhost = net_misc.pack_address((host, tcpport, ))
            if _Debug:
                lg.out(_DebugLevel, '    sending to %r via TCP' % srvhost)
            dlist.append(tcp_node.send(
                sendfilename, srvhost, 'Identity', keep_alive=False,
            ))
        return DeferredList(dlist, fireOnOneCallback=True)

#------------------------------------------------------------------------------

def main():
    import sys
    from system import bpio
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    from twisted.internet import reactor  # @UnresolvedImport
    ir = IdRotator()
    ir.addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='DONE')  # @UndefinedVariable
    ir.addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='FAILED')  # @UndefinedVariable
    reactor.callWhenRunning(ir.automat, 'run')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
