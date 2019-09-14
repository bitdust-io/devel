#!/usr/bin/env python
# holler.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (online_status.py) is part of BitDust Software.
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
.. module:: holler
.. role:: red

BitDust holler() Automat

EVENTS:
    * :red:`ack-received`
    * :red:`ack-timeout`
    * :red:`cache-and-ping`
    * :red:`fail-received`
    * :red:`ping`
    * :red:`remote-identity-cached`
    * :red:`remote-identity-failed`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from lib import strng
from lib import packetid

from automats import automat

from contacts import identitycache

from crypt import signed

from p2p import commands

from transport import gateway

from userid import global_id
from userid import id_url
from userid import my_id

#------------------------------------------------------------------------------

def ping(idurl, ack_timeout=10, cache_timeout=5, cache_retries=2, ping_retries=2, force_cache=False):
    result = Deferred()
    h = Holler(
        remote_idurl=id_url.field(idurl),
        result_defer=result,
        ack_timeout=ack_timeout,
        cache_timeout=cache_timeout,
        cache_retries=cache_retries,
        ping_retries=ping_retries,
        debug_level=_DebugLevel,
        log_events=_Debug,
        log_transitions=_Debug,
    )
    if force_cache:
        h.automat('cache-and-ping')
    else:
        h.automat('ping')
    return result

#------------------------------------------------------------------------------

class Holler(automat.Automat):
    """
    This class implements all the functionality of ``holler()`` state machine.
    """

    def __init__(self, remote_idurl, result_defer, ack_timeout, cache_timeout, cache_retries, ping_retries,
                 debug_level=0, log_events=False, log_transitions=False, publish_events=False, **kwargs):
        """
        Builds `holler()` state machine.
        """
        self.remote_idurl = remote_idurl
        self.result_defer = result_defer
        self.ack_timeout = ack_timeout
        self.cache_timeout = cache_timeout
        self.cache_retries = cache_retries
        self.ping_retries = ping_retries
        super(Holler, self).__init__(
            name="holler_%s" % global_id.idurl2glob(self.remote_idurl),
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
        at creation phase of `holler()` machine.
        """
        self.cache_attempts = 0
        self.ping_attempts = 0

    def state_changed(self, oldstate, newstate, event, *args, **kwargs):
        """
        Method to catch the moment when `holler()` state were changed.
        """

    def state_not_changed(self, curstate, event, *args, **kwargs):
        """
        This method intended to catch the moment when some event was fired in the `holler()`
        but automat state was not changed.
        """

    def A(self, event, *args, **kwargs):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'cache-and-ping' or ( event == 'ping' and not self.isCached(*args, **kwargs) ):
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
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'fail-received':
                self.state = 'FAILED'
                self.doReportFailed(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-received':
                self.state = 'SUCCESS'
                self.doReportSuccess(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and not self.isMorePingRetries(*args, **kwargs):
                self.state = 'TIMEOUT'
                self.doReportTimeOut(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'ack-timeout' and self.isMorePingRetries(*args, **kwargs):
                self.doSendMyIdentity(*args, **kwargs)
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
        idcache_defer = identitycache.immediatelyCaching(strng.to_text(self.remote_idurl), timeout=self.cache_timeout)
        idcache_defer.addCallback(lambda src: self.automat('remote-identity-cached', src))
        idcache_defer.addErrback(lambda err: self.automat('remote-identity-failed', err))

    def doSendMyIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self.ping_attempts += 1
        ping_packet = signed.Packet(
            Command=commands.Identity(),
            OwnerID=my_id.getLocalID(),
            CreatorID=my_id.getLocalID(),
            PacketID=('identity:%s' % packetid.UniqueID()),
            Payload=strng.to_bin(my_id.getLocalIdentity().serialize()),
            RemoteID=self.remote_idurl,
        )
        gateway.outbox(ping_packet, wide=True, response_timeout=self.ack_timeout, callbacks={
            commands.Ack(): lambda response, info: self.automat('ack-received', response, info),
            commands.Fail(): lambda response, info: self.automat('fail-received', response, info),
            None: lambda pkt_out: self.automat('ack-timeout', pkt_out),
        })

    def doReportNoIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('failed to cache remote identity %s after %d attempts' % (
            self.remote_idurl, self.cache_attempts, ))
        self.result_defer.errback(Exception('failed to cache remote identity %s after %d attempts' % (
            self.remote_idurl, self.cache_attempts, )))

    def doReportFailed(self, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('ping failed because received Fail() from remote user %s' % self.remote_idurl)
        self.result_defer.errback(Exception('ping failed because received Fail() from remote user %s' % self.remote_idurl))

    def doReportTimeOut(self, *args, **kwargs):
        """
        Action method.
        """
        lg.warn('remote user %s did not responded after %d ping attempts' % (self.remote_idurl, self.ping_attempts, ))
        self.result_defer.errback(Exception('remote user %s did not responded after %d ping attempts' % (
            self.remote_idurl, self.ping_attempts, )))

    def doReportSuccess(self, *args, **kwargs):
        """
        Action method.
        """
        self.result_defer.callback((args[0], args[1], ))

    def doDestroyMe(self, *args, **kwargs):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.remote_idurl = None
        self.result_defer = None
        self.ack_timeout = None
        self.cache_timeout = None
        self.cache_retries = None
        self.ping_retries = None
        self.destroy()

