#!/usr/bin/env python
# handshaker.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (handshaker.py) is part of BitDust Software.
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
.. module:: handshaker
.. role:: red

BitDust handshaker() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`ack-timeout`
    * :red:`cache-and-ping`
    * :red:`cancel`
    * :red:`fail-received`
    * :red:`outbox-failed`
    * :red:`ping`
    * :red:`remote-identity-cached`
    * :red:`remote-identity-failed`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 20

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import packetid

from bitdust.automats import automat

from bitdust.main import settings

from bitdust.contacts import identitycache

from bitdust.crypt import signed

from bitdust.p2p import commands

from bitdust.transport import packet_out
from bitdust.transport import gateway

from bitdust.userid import global_id
from bitdust.userid import my_id

#------------------------------------------------------------------------------

_RunningHandshakers = {}
_KnownChannels = {}

#------------------------------------------------------------------------------


def ping(
    idurl,
    ack_timeout=None,
    cache_timeout=15,
    cache_retries=2,
    ping_retries=2,
    force_cache=False,
    skip_outbox=False,
    keep_alive=True,
    fake_identity=None,
    channel='identity',
    channel_counter=True,
    cancel_running=False,
):
    """
    Doing peer-to-peer ping with acknowledgment and return `Deferred` object to receive result.
    First read remote identity file from `idurl` location.
    Then sending my own identity to remote node and wait for ack.
    If Ack() packet from remote node times out (or another error happened)
    should return failed result in the result `Deferred`.
    """
    global _RunningHandshakers
    remote_idurl = strng.to_bin(idurl)
    if not remote_idurl:
        raise Exception('empty idurl provided')
    result = Deferred()
    pending_results = []
    if remote_idurl in _RunningHandshakers:
        if cancel_running:
            running_info = _RunningHandshakers.pop(remote_idurl)
            inst = running_info.pop('instance')
            pending_results = running_info.pop('results')
            if inst:
                inst.automat('cancel')
        else:
            _RunningHandshakers[remote_idurl]['results'].append(result)
            if _Debug:
                lg.args(_DebugLevel, already_opened=True, idurl=remote_idurl, channel=channel, skip_outbox=skip_outbox)
            return result
    pending_results += [
        result,
    ]
    _RunningHandshakers[remote_idurl] = {
        'instance': None,
        'results': pending_results,
    }
    if _Debug:
        lg.args(_DebugLevel, already_opened=False, idurl=remote_idurl, channel=channel, skip_outbox=skip_outbox, pending_results=len(pending_results))
    h = Handshaker(
        remote_idurl=remote_idurl,
        ack_timeout=ack_timeout,
        cache_timeout=cache_timeout,
        cache_retries=cache_retries,
        ping_retries=ping_retries,
        skip_outbox=skip_outbox,
        keep_alive=keep_alive,
        fake_identity=fake_identity,
        channel=channel,
        channel_counter=channel_counter,
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
    )
    _RunningHandshakers[remote_idurl]['instance'] = h
    if force_cache:
        h.automat('cache-and-ping')
    else:
        h.automat('ping')
    return result


def is_running(idurl):
    """
    Returns True if some "ping" is currently running towards given user.
    """
    global _RunningHandshakers
    remote_idurl = strng.to_bin(idurl)
    if not remote_idurl:
        return False
    return remote_idurl in _RunningHandshakers


def get_info(idurl):
    """
    If there is a running handshake with given idurl will return its instance.
    """
    global _RunningHandshakers
    remote_idurl = strng.to_bin(idurl)
    if not remote_idurl:
        return None
    return _RunningHandshakers.get(remote_idurl)


def cancel_all():
    global _RunningHandshakers
    for remote_idurl in list(_RunningHandshakers.keys()):
        h = (_RunningHandshakers.get(remote_idurl, {}) or {}).get('instance')
        if h:
            h.event('cancel')


#------------------------------------------------------------------------------


def on_identity_packet_outbox_status(pkt_out, status, error):
    global _RunningHandshakers
    remote_idurl = strng.to_bin(pkt_out.outpacket.RemoteID)
    if remote_idurl in _RunningHandshakers:
        inst = _RunningHandshakers[remote_idurl]['instance']
        if inst:
            if status == 'finished':
                inst.automat('identity-sent', pkt_out)
            else:
                inst.automat('outbox-failed', status=status, error=error)


#------------------------------------------------------------------------------


class Handshaker(automat.Automat):

    """
    This class implements all the functionality of ``handshaker()`` state machine.
    """

    def __init__(
        self, remote_idurl, ack_timeout, cache_timeout, cache_retries, ping_retries, skip_outbox, keep_alive, fake_identity, channel, channel_counter, debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs
    ):
        """
        Builds `handshaker()` state machine.
        """
        global _KnownChannels
        self.remote_idurl = strng.to_bin(remote_idurl)
        self.remote_global_id = global_id.idurl2glob(self.remote_idurl)
        self.ack_timeout = ack_timeout
        if not self.ack_timeout:
            self.ack_timeout = settings.P2PTimeOut()
        self.cache_timeout = cache_timeout
        self.cache_retries = cache_retries
        self.ping_retries = ping_retries
        self.skip_outbox = skip_outbox
        self.keep_alive = keep_alive
        self.fake_identity = fake_identity
        self.channel = channel
        self.channel_counter = channel_counter
        if self.channel not in _KnownChannels:
            _KnownChannels[self.channel] = 0
        _KnownChannels[self.channel] += 1
        super(Handshaker, self).__init__(
            name='handshake_%s%d_%s' % (self.channel.replace('_', ''), _KnownChannels[self.channel], self.remote_global_id), state='AT_STARTUP', debug_level=debug_level, log_events=log_events, log_transitions=log_transitions,
            publish_events=publish_events, **kwargs
        )

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of `handshaker()` machine.
        """
        self.cache_attempts = 0
        self.ping_attempts = 0

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'cache-and-ping' or (event == 'ping' and not self.isCached(*args, **kwargs)):
                self.state = 'CACHE'
                self.doInit(*args, **kwargs)
                self.doCacheRemoteIDURL(*args, **kwargs)
            elif event == 'ping' and self.isCached(*args, **kwargs):
                self.state = 'ACK?'
                self.doInit(*args, **kwargs)
                self.doSendMyIdentity(*args, **kwargs)
        #---CACHE---
        elif self.state == 'CACHE':
            if event == 'remote-identity-failed' and not self.isMoreCacheRetries(*args, **kwargs):
                self.state = 'NO_IDENT'
                self.doReportNoIdentity(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'remote-identity-failed' and self.isMoreCacheRetries(*args, **kwargs):
                self.doCacheRemoteIDURL(*args, **kwargs)
            elif event == 'remote-identity-cached':
                self.state = 'ACK?'
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'NO_IDENT'
                self.doDestroyMe(*args, **kwargs)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'ack-received':
                self.state = 'SUCCESS'
                self.doReportSuccess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and not self.isMorePingRetries(*args, **kwargs):
                self.state = 'TIMEOUT'
                self.doReportTimeOut(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and self.isMorePingRetries(*args, **kwargs):
                self.doSendMyIdentity(*args, **kwargs)
            elif event == 'fail-received' or event == 'outbox-failed':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'cancel':
                self.state = 'NO_IDENT'
                self.doDestroyMe(*args, **kwargs)
        #---SUCCESS---
        elif self.state == 'SUCCESS':
            pass
        #---TIMEOUT---
        elif self.state == 'TIMEOUT':
            pass
        #---NO_IDENT---
        elif self.state == 'NO_IDENT':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        return None

    def isCached(self, *args, **kwargs):
        """
        Condition method.
        """
        return identitycache.HasKey(self.remote_idurl)

    def isMoreCacheRetries(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.cache_attempts <= self.cache_retries

    def isMorePingRetries(self, *args, **kwargs):
        """
        Condition method.
        """
        return self.ping_attempts <= self.ping_retries

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """

    def doCacheRemoteIDURL(self, *args, **kwargs):
        """
        Action method.
        """
        self.cache_attempts += 1
        idcache_defer = identitycache.immediatelyCaching(idurl=strng.to_text(self.remote_idurl), timeout=self.cache_timeout)
        idcache_defer.addCallback(lambda src: self.automat('remote-identity-cached', src))
        idcache_defer.addErrback(lambda err: self.automat('remote-identity-failed', err) and None)

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        global _KnownChannels
        self.ping_attempts += 1
        if self.fake_identity:
            identity_object = self.fake_identity
        else:
            identity_object = my_id.getLocalIdentity()
        if not identity_object.Valid():
            raise Exception('can not use invalid identity for ping')
        if self.channel_counter:
            packet_id = '%s:%d:%d:%s' % (self.channel, _KnownChannels[self.channel], self.ping_attempts, packetid.UniqueID())
        else:
            packet_id = '%s:%d:%s' % (self.channel, self.ping_attempts, packetid.UniqueID())
        ping_packet = signed.Packet(
            Command=commands.Identity(),
            OwnerID=my_id.getIDURL(),
            CreatorID=my_id.getIDURL(),
            PacketID=packet_id,
            Payload=strng.to_bin(identity_object.serialize()),
            RemoteID=self.remote_idurl,
        )
        if self.skip_outbox:
            packet_out.create(
                outpacket=ping_packet,
                wide=True,
                response_timeout=self.ack_timeout,
                callbacks={
                    commands.Ack(): lambda response, info: self.automat('ack-received', response=response, info=info),
                    commands.Fail(): lambda response, info: self.automat('fail-received', response=response, info=info),
                    None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
                },
                keep_alive=self.keep_alive,
            )
        else:
            gateway.outbox(
                outpacket=ping_packet,
                wide=True,
                response_timeout=self.ack_timeout,
                callbacks={
                    commands.Ack(): lambda response, info: self.automat('ack-received', response=response, info=info),
                    commands.Fail(): lambda response, info: self.automat('fail-received', response=response, info=info),
                    None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
                },
                keep_alive=self.keep_alive,
            )
        if _Debug:
            lg.args(_DebugLevel, packet_id=packet_id, remote_idurl=self.remote_idurl, ping_attempts=self.ping_attempts)

    def doReportNoIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        global _RunningHandshakers
        lg.warn('failed to cache remote identity %r after %d attempts' % (self.remote_idurl, self.cache_attempts))
        if self.remote_idurl in _RunningHandshakers:
            for result_defer in _RunningHandshakers[self.remote_idurl]['results']:
                if not result_defer.called:
                    result_defer.errback(Exception('failed to cache remote identity %r after %d attempts' % (
                        self.remote_idurl,
                        self.cache_attempts,
                    ), ))

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        global _RunningHandshakers
        response = kwargs.get('response')
        info = kwargs.get('info')
        if response and info:
            lg.warn('handshake failed because received Fail() from remote user %r : %r' % (response, info))
            if self.remote_idurl in _RunningHandshakers:
                for result_defer in _RunningHandshakers[self.remote_idurl]['results']:
                    if not result_defer.called:
                        result_defer.errback(Exception('handshake failed because received Fail() packet from remote user'))
            return
        status = kwargs.get('status')
        error = kwargs.get('error')
        if status == 'cancelled':
            lg.warn('handshake was cancelled, my Identity() packet was not sent to %r : %r' % (self.remote_idurl, error))
        else:
            lg.err('handshake failed with status %r, my Identity() packet was not sent to remote user %r : %r' % (status, self.remote_idurl, error))
        if self.remote_idurl in _RunningHandshakers:
            for result_defer in _RunningHandshakers[self.remote_idurl]['results']:
                if not result_defer.called:
                    result_defer.errback(Exception('handshake failed, request packet was not sent to remote node'))

    def doReportTimeOut(self, *args, **kwargs):
        """
        Action method.
        """
        global _RunningHandshakers
        lg.warn('remote node %r did not respond after %d ping attempts' % (self.remote_global_id, self.ping_attempts))
        if self.remote_idurl in _RunningHandshakers:
            for result_defer in _RunningHandshakers[self.remote_idurl]['results']:
                if not result_defer.called:
                    result_defer.errback(Exception('remote node %s did not respond after %d ping attempt(s)' % (
                        self.remote_global_id,
                        self.ping_attempts,
                    ), ))

    def doReportSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        global _RunningHandshakers
        response = kwargs.get('response')
        info = kwargs.get('info')
        if _Debug:
            lg.args(_DebugLevel, channel=self.channel, idurl=self.remote_idurl, response=response, info=info)
        if self.remote_idurl in _RunningHandshakers:
            for result_defer in _RunningHandshakers[self.remote_idurl]['results']:
                if not result_defer.called:
                    result_defer.callback((
                        response,
                        info,
                    ))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        global _RunningHandshakers
        if self.remote_idurl in _RunningHandshakers:
            _RunningHandshakers[self.remote_idurl]['instance'] = None
            _RunningHandshakers[self.remote_idurl]['results'] = []
            _RunningHandshakers.pop(self.remote_idurl)
        else:
            lg.warn('did not found registered Handshaker() instance for %r' % self.remote_idurl)
        self.remote_idurl = None
        self.ack_timeout = None
        self.cache_timeout = None
        self.cache_retries = None
        self.ping_retries = None
        self.skip_outbox = None
        self.fake_identity = None
        self.channel = None
        self.channel_counter = None
        self.destroy()
