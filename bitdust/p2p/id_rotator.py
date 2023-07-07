#!/usr/bin/env python
# id_rotator.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
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
    * :red:`auto-rotate-disabled`
    * :red:`check`
    * :red:`found-new-id-source`
    * :red:`id-server-failed`
    * :red:`my-id-exist`
    * :red:`my-id-failed`
    * :red:`my-id-sent`
    * :red:`my-id-updated`
    * :red:`need-more-sources`
    * :red:`no-id-servers-found`
    * :red:`ping-done`
    * :red:`ping-failed`
    * :red:`run`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = False
_DebugLevel = 10

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import sys as _s, os.path as _p
    _s.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(_s.argv[0])), '..')))

#------------------------------------------------------------------------------

import random

from twisted.internet.defer import Deferred, DeferredList, CancelledError  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.automats import automat

from bitdust.lib import net_misc
from bitdust.lib import nameurl
from bitdust.lib import strng

from bitdust.main import config
from bitdust.main import settings

from bitdust.userid import identity
from bitdust.userid import known_servers
from bitdust.userid import my_id

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


def run(preferred_servers={}, force=False):
    """
    Executes id_rotator() state machine to test my identity sources and if needed republish my identity
    on another ID server in case current situation with ID sources "is not healthy".
    Input parameter "preferred_servers" can be used to control which servers to be used
    when replacing a dead one.
    Returns True/False via deferred object to report result.
    """
    result_defer = Deferred()
    ir = IdRotator()
    ir.automat('run', result_defer=result_defer, preferred_servers=preferred_servers, force=force)
    return result_defer


#------------------------------------------------------------------------------


class IdRotator(automat.Automat):
    """
    This class implements all the functionality of ``id_rotator()`` state machine.
    """
    def __init__(self, debug_level=_DebugLevel, log_events=_Debug, log_transitions=_Debug, publish_events=True, **kwargs):
        """
        Builds `id_rotator()` state machine.
        """
        super(IdRotator, self).__init__(name='id_rotator', state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions, publish_events=publish_events, **kwargs)

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `id_rotator()` machine.
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
            elif event == 'ping-done' and (self.isChecking(*args, **kwargs) or self.isHealthy(*args, **kwargs)):
                self.state = 'DONE'
                self.doReportDone(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ping-done' and not self.isChecking(*args, **kwargs) and not self.isHealthy(*args, **kwargs):
                self.state = 'NEW_SOURCE!'
                self.doSelectNewIDServer(*args, **kwargs)
        #---NEW_SOURCE!---
        elif self.state == 'NEW_SOURCE!':
            if event == 'found-new-id-source':
                self.state = 'MY_ID_ROTATE'
                self.doRebuildMyIdentity(*args, **kwargs)
            elif event == 'no-id-servers-found' or event == 'auto-rotate-disabled':
                self.state = 'FAILED'
                self.doReportFailed(event, *args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
        #---MY_ID_ROTATE---
        elif self.state == 'MY_ID_ROTATE':
            if event == 'my-id-updated':
                self.state = 'SEND_ID'
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'need-more-sources':
                self.state = 'NEW_SOURCE!'
                self.doSelectNewIDServer(*args, **kwargs)
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
            elif event == 'id-server-failed' or (event == 'my-id-exist' and not self.isMyIdentityValid(*args, **kwargs)):
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
        if self.force:
            # this way we can execute "rotate" flow even if all identity sources are healthy
            return False
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
        self.old_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        self.known_servers = known_servers.by_host()
        self.preferred_servers = kwargs.get('preferred_servers', {})
        self.possible_sources = []
        if _Debug:
            lg.args(_DebugLevel, preferred_servers=self.preferred_servers)
        self.force = kwargs.get('force', False)
        self.new_revision = kwargs.get('new_revision')
        self.rotated = False
        if not self.preferred_servers:
            try:
                for srv in strng.to_text(config.conf().getString('services/identity-propagate/known-servers')).split(','):
                    if srv.strip():
                        parts = srv.strip().split(':')
                        if len(parts) == 2:
                            host, web_port = parts
                            tcp_port = settings.IdentityServerPort()
                        else:
                            host, web_port, tcp_port = parts
                        self.preferred_servers[host] = (
                            int(web_port),
                            int(tcp_port),
                        )
            except:
                lg.exc()
        self.preferred_servers = {strng.to_bin(k): v for k, v in self.preferred_servers.items()}
        self.current_servers = []
        for idurl in my_id.getLocalIdentity().getSources(as_originals=True):
            self.current_servers.append(strng.to_bin(nameurl.GetHost(idurl)))
        if _Debug:
            lg.args(_DebugLevel, known_servers=self.known_servers, preferred_servers=self.preferred_servers, current_servers=self.current_servers)

    def doPingMyIDServers(self, *args, **kwargs):
        """
        Action method.
        """
        self._do_verify_my_sources()

    def doSelectNewIDServer(self, *args, **kwargs):
        """
        Action method.
        """
        if not self.force and not config.conf().getBool('services/identity-propagate/automatic-rotate-enabled'):
            self.automat('auto-rotate-disabled')
            return

        target_servers = self.preferred_servers
        if not target_servers:
            target_servers = self.known_servers
        # make sure to not choose a server I already have in my ID sources
        for current_server in self.current_servers:
            if current_server in target_servers:
                target_servers.pop(current_server)

        if not target_servers:
            self.automat('no-id-servers-found')
            return

        target_servers = {strng.to_bin(k): v for k, v in target_servers.items()}
        target_hosts = list(target_servers.keys())
        random.shuffle(target_hosts)
        if _Debug:
            lg.args(_DebugLevel, target_hosts=target_hosts, current_servers=self.current_servers, target_servers=target_servers)

        def _new_idurl_exist(idsrc, new_idurl, pos):
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._new_idurl_exist %r already with same name' % new_idurl)
            latest_revision = my_id.getLocalIdentity().getRevisionValue()
            try:
                existing_identity_with_same_name = identity.identity(xmlsrc=idsrc)
                if not existing_identity_with_same_name.isCorrect():
                    raise Exception('remote identity not correct at position %r' % pos)
                if not existing_identity_with_same_name.Valid():
                    raise Exception('remote identity not valid at position %r' % pos)
            except:
                lg.exc()
                if pos + 1 >= len(target_hosts):
                    self.automat('no-id-servers-found')
                else:
                    _ping_one_server(pos + 1)
                return
            if existing_identity_with_same_name.getPublicKey() == my_id.getLocalIdentity().getPublicKey():
                if latest_revision <= existing_identity_with_same_name.getRevisionValue():
                    self.new_revision = max(self.new_revision or -1, existing_identity_with_same_name.getRevisionValue() + 1)
                lg.info('found my own identity on "old" ID server and will re-use that source again: %r' % new_idurl)
                if new_idurl not in self.possible_sources:
                    self.possible_sources.append(new_idurl)
                self.automat('found-new-id-source', new_idurl)
                return

            if pos + 1 >= len(target_hosts):
                self.automat('no-id-servers-found')
            else:
                _ping_one_server(pos + 1)

        def _new_idurl_not_exist(err, new_idurl):
            lg.info('found new identity source available to use: %r' % new_idurl)
            if new_idurl not in self.possible_sources:
                self.possible_sources.append(new_idurl)
            self.automat('found-new-id-source', new_idurl)

        def _server_replied(htmlsrc, host, pos):
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._server_replied %r' % host)
            webport, _ = target_servers[host]
            if webport == 80:
                webport = ''
            new_idurl = nameurl.UrlMake('http', strng.to_text(host), webport, my_id.getIDName() + '.xml')
            d = net_misc.getPageTwisted(new_idurl, timeout=15)
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
            tcpport = int(tcpport)
            server_url = nameurl.UrlMake('http', strng.to_text(host), webport, '')
            if _Debug:
                lg.out(_DebugLevel, 'id_rotator.doSelectNewIDServer._ping_one_server at %s known tcp port is %d' % (server_url, tcpport))
            d = net_misc.getPageTwisted(server_url, timeout=15)
            d.addCallback(_server_replied, host, pos)
            d.addErrback(_server_failed, host, pos)

        _ping_one_server(0)

    def doRebuildMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        min_servers = max(
            settings.MinimumIdentitySources(),
            config.conf().getInt('services/identity-propagate/min-servers') or settings.MinimumIdentitySources(),
        )
        max_servers = min(
            settings.MaximumIdentitySources(),
            config.conf().getInt('services/identity-propagate/max-servers') or settings.MaximumIdentitySources(),
        )
        current_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        current_contacts = list(my_id.getLocalIdentity().getContacts())
        new_sources = []
        new_idurl = strng.to_bin(args[0])
        if _Debug:
            lg.args(_DebugLevel, current_sources=current_sources, alive_idurls=self.alive_idurls, new_idurl=new_idurl)
        # first get rid of "dead" sources
        for current_idurl in current_sources:
            if current_idurl not in self.alive_idurls:
                continue
            if strng.to_bin(current_idurl) in new_sources:
                continue
            new_sources.append(strng.to_bin(current_idurl))
        if self.force and len(new_sources) == len(current_sources):
            # do not increase number of identity sources, only rotate them
            new_sources.pop(0)
        # and add new "good" source to the end of the list
        if new_idurl and new_idurl not in new_sources:
            new_sources.append(new_idurl)
        if _Debug:
            lg.args(_DebugLevel, new_sources=new_sources, min_servers=min_servers, max_servers=max_servers)
        if len(new_sources) > max_servers:
            all_new_sources = list(new_sources)
            new_sources = new_sources[max(0, len(new_sources) - max_servers):]
            lg.warn('skip %d identity sources, require maximum %d sources' % (len(all_new_sources) - len(new_sources), max_servers))
        if len(new_sources) < min_servers:
            additional_sources = self.possible_sources[:min_servers - len(new_sources)]
            if additional_sources:
                lg.warn('additional sources to be used: %r' % additional_sources)
                new_sources.extend(additional_sources)
        unique_sources = []
        for idurl_bin in new_sources:
            if strng.to_bin(idurl_bin) not in unique_sources:
                unique_sources.append(strng.to_bin(idurl_bin))
        if len(unique_sources) < min_servers:
            lg.warn('not enough identity sources, need to rotate again')
            self.automat('need-more-sources')
            return
        contacts_changed = False
        id_changed = my_id.rebuildLocalIdentity(
            new_sources=unique_sources,
            new_revision=self.new_revision,
        )
        new_contacts = my_id.getLocalIdentity().getContacts()
        if len(current_contacts) != len(new_contacts):
            contacts_changed = True
        if not contacts_changed:
            for pos in range(len(current_contacts)):
                if current_contacts[pos] != new_contacts[pos]:
                    contacts_changed = True
                    break
        self.rotated = True
        if _Debug:
            lg.args(_DebugLevel, new_sources=new_sources, contacts_changed=contacts_changed, id_changed=id_changed)
        self.automat('my-id-updated', (contacts_changed, id_changed))

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
            if _Debug:
                lg.args(_DebugLevel, results=results)
            # TODO: validate my identity in all responses
            self.automat('my-id-exist', results)
            return results

        def _eb(err):
            lg.err(err)
            self.automat('my-id-not-exist', err)
            if err.type == CancelledError:
                return None
            return err

        dl = []
        for idurl in my_id.getLocalIdentity().getSources(as_originals=True):
            dl.append(net_misc.getPageTwisted(idurl, timeout=15))
        d = DeferredList(dl, consumeErrors=True)
        d.addCallback(_cb)
        d.addErrback(_eb)

    def doReportDone(self, event, *args, **kwargs):
        """
        Action method.
        """
        if not self.result_defer:
            return
        if event == 'ping-done':
            self.result_defer.callback((self._is_healthy(args[0]), False))
        elif event == 'my-id-exist':
            self.result_defer.callback((
                True,
                self.rotated,
            ))
            # if self.rotated:
            #     events.send('my-identity-rotate-complete', data=dict())

    def doReportFailed(self, event, *args, **kwargs):
        """
        Action method.
        """
        result = args[0] if args else None
        lg.warn('id_rotator finished with failed result %r : %r' % (event, result))
        if not self.result_defer:
            return
        if event == 'auto-rotate-disabled':
            self.result_defer.errback(Exception('identity not healthy, but automatic rotate disabled'))
            return
        if event == 'no-id-servers-found':
            lg.warn('no more available identity servers found')
            self.result_defer.errback(Exception('no more available identity servers found'))
            return
        lg.err(result)
        self.result_defer.errback(result)

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
        self.possible_sources = None
        self.destroy()

    def _is_healthy(self, ping_results):
        # TODO: for now simply check that first identity server in my identity is alive
        # we can implement more "aggressive" checks later...
        # for example if any of my sources is not alive -> replace him also
        # also we can check here if I have enough sources according to those configs:
        #     services/identity-propagate/min-servers
        #     services/identity-propagate/max-servers
        if not ping_results:
            return False
        if not bool(ping_results[0]):
            return False
        unique_idurls = []
        for idurl in ping_results:
            if idurl not in unique_idurls:
                unique_idurls.append(idurl)
        min_servers = max(
            settings.MinimumIdentitySources(),
            config.conf().getInt('services/identity-propagate/min-servers') or settings.MinimumIdentitySources(),
        )
        max_servers = min(
            settings.MaximumIdentitySources(),
            config.conf().getInt('services/identity-propagate/max-servers') or settings.MaximumIdentitySources(),
        )
        if _Debug:
            lg.args(_DebugLevel, min_servers=min_servers, max_servers=max_servers, ping_results=ping_results, unique_idurls=unique_idurls)
        if len(unique_idurls) != len(ping_results):
            return False
        if len(unique_idurls) < min_servers:
            return False
        if len(unique_idurls) > max_servers:
            return False
        return True

    def _do_check_ping_results(self, ping_results):
        self.alive_idurls = []
        my_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        local_revision = my_id.getLocalIdentity().getRevisionValue()
        latest_revision = -1
        pos = -1
        for result, remote_identity_src in ping_results:
            pos += 1
            idurl_bin = my_sources[pos]
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
                if latest_revision <= remote_ident.getRevisionValue():
                    latest_revision = remote_ident.getRevisionValue()
            except:
                lg.exc(remote_identity_src)
                self.alive_idurls.append(None)
                continue
            if idurl_bin not in self.alive_idurls:
                self.alive_idurls.append(idurl_bin)
        if not self.new_revision:
            self.new_revision = max(local_revision, latest_revision) + 1
        if _Debug:
            lg.args(_DebugLevel, new_revision=self.new_revision, alive_idurls=self.alive_idurls)

        if not self.alive_idurls or not list(filter(None, self.alive_idurls)):
            # so all my id sources are down
            # if no alive sources found then probably network is down
            # and we should not do anything at the moment
            # but we must also check in that case if any of my ID servers are still alive, but only my identity was removed
            # otherwise we can get situation when all my id servers are UP, but my identity just expired and id_rotator do nothing to fix that
            self._fallback_and_ping_my_servers()
            return

        self.automat('ping-done', self.alive_idurls)

    def _do_send_my_identity(self):
        """
        Send my updated identity to the identity servers to register it.
        """
        my_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        payload = my_id.getLocalIdentity().serialize(as_text=False)
        dlist = []
        if _Debug:
            lg.out(_DebugLevel, 'id_rotator._do_send_my_identity my_sources=%r' % my_sources)
        for idurl_bin in my_sources:
            _, host, _webport, filename = nameurl.UrlParse(idurl_bin)
            webport = None
            if host in self.preferred_servers:
                webport = int(self.preferred_servers[host][0])
            if not webport and host in self.known_servers:
                webport = int(self.known_servers[host][0])
            if not webport:
                webport = _webport
            url = net_misc.pack_address(
                (
                    host,
                    webport,
                ),
                proto='http',
            )
            dlist.append(net_misc.http_post_data(
                url=url,
                data=payload,
                connectTimeout=15,
            ))
            if _Debug:
                lg.args(_DebugLevel, url=url, filename=filename, size=len(payload))
        return DeferredList(dlist, fireOnOneCallback=True)

    def _do_verify_my_sources(self):
        my_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        dl = []
        for idurl_bin in my_sources:
            d = net_misc.getPageTwisted(idurl_bin, timeout=15)
            dl.append(d)
        d = DeferredList(dl, consumeErrors=True)
        d.addCallback(self._do_check_ping_results)
        d.addErrback(lambda err: self.automat('ping-failed', err))

    def _fallback_and_ping_my_servers(self):
        """
        Just ping all my id servers by sending a HTTP request to the "main page".
        """
        my_sources = my_id.getLocalIdentity().getSources(as_originals=True)
        id_servers = []
        for idurl_bin in my_sources:
            proto, host, port, _ = nameurl.UrlParse(idurl_bin)
            id_servers.append(nameurl.UrlMake(proto, host, port, ''))
        if _Debug:
            lg.args(_DebugLevel, id_servers=id_servers)
        dl = []
        for url in id_servers:
            d = net_misc.getPageTwisted(url, timeout=15)
            dl.append(d)
        d = DeferredList(dl, consumeErrors=True)
        d.addCallback(lambda result: self.automat('ping-done', []))
        d.addErrback(self._fallback_check_network_connected)

    def _fallback_check_network_connected(self, err):
        if _Debug:
            lg.args(_DebugLevel, err)
        from bitdust.p2p import network_connector
        if network_connector.A().state != 'CONNECTED':
            self.automat('ping-failed', err)
        else:
            self.automat('ping-done', [])


#------------------------------------------------------------------------------


def main():
    from bitdust.system import bpio
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    from twisted.internet import reactor  # @UnresolvedImport
    ir = IdRotator()
    ir.addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='DONE')  # @UndefinedVariable
    ir.addStateChangedCallback(lambda *a: reactor.stop(), oldstate=None, newstate='FAILED')  # @UndefinedVariable
    reactor.callWhenRunning(ir.automat, 'run')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
