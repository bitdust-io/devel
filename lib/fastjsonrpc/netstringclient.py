#!/usr/bin/env python
"""
Copyright 2012 Tadeas Moravec.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


==============
JSONRPC Server
==============

Provides JSONRPCServer class, which can be used to expose methods via RPC.
"""

from __future__ import absolute_import
from twisted.protocols import basic
from twisted.python import log
from twisted.internet.protocol import Factory
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.defer import Deferred

from . import jsonrpc


class CallbackProtocol(basic.NetstringReceiver):
    """
    Protocol with callback.

    It will call given callback after it receives full data.
    """

    def __init__(self, callback):
        """
        @type callback: callable
        @param callback: Callable to call with string we have received
        """

        self.callback = callback

    def stringReceived(self, string):
        """
        Call our callback with string we have received and close connection.

        @type string: str|unicode
        @param string: The netstring we have received, striped of the
            netstring stuff
        """

        self.callback(string)
        self.transport.loseConnection()


class CallbackFactory(Factory):
    """
    Factory with callback.

    It will call given callback after the protocol receives full data.
    """

    def __init__(self, callback):
        """
        @type callback: callable
        @param callback: Callable to call when our Protocol called us with
            some data
        """

        self.callback = callback

    def buildProtocol(self, _):
        """
        We need to pass our callback to the CallbackProtocol's constructor,
        so we cannot just use CallbackFactory.protocol = CallbackProtocol.

        The _ argument is here just to satisfy the interface, we don't use it.
        """

        return CallbackProtocol(self.responseReceived)

    def responseReceived(self, string):
        """
        This is what the Protocol calls after it receives data. We just pass it
        to whatever callback we were given.

        @type string: mixed
        @param string: what the Protocol received and we pass on
        """

        self.callback(string)


class ResponseDeferred(Deferred):
    """
    Deferred the client gets.

    Proxy.callRemote returns an instance of this. It fires 'itself'
    after the factory calls responseReceived.
    """

    def __init__(self, verbose=False):
        """
        Remember verbosity level for potential logging.

        @type verbose: bool
        @param verbose: If True, we log the response JSON
        """

        Deferred.__init__(self)
        self.verbose = verbose

    def responseReceived(self, json_response):
        """
        This gets called by the factory after we received a response. We decode
        it and fire with result.

        @type json_response: str|unicode
        @param json_response: The response from the server
        """

        if self.verbose:
            log.msg('Response received: %s' % json_response)

        self.callback(json_response)


class Proxy(object):
    """
    A proxy to one specific JSON-RPC server. Pass the server URL to the
    constructor and call proxy.callRemote('method', *args) to call 'method'
    with *args or **kwargs.

    @TODO callRemote should not set any self.* attributes, else multiple
        callRemote calls will fire the same deferred twice..
        self.response_deferred is THE problem ;-)
    """

    def __init__(self, url, version=jsonrpc.VERSION_1, timeout=None,
                 verbose=False):
        """
        @type url: str
        @param url: URL of the RPC server, including the port

        @type version: float
        @param version: Which JSON-RPC version to use? Defaults to version 1.

        @type timeout: int
        @param timeout: Timeout of the call in seconds

        @type verbose: bool
        @param verbose: If True, we log the outgoing and incoming JSON
        """

        self.hostname, self.port = url.split(':')
        self.port = int(self.port)
        self.version = version
        self.timeout = timeout
        self.verbose = verbose

    def connectionMade(self, protocol, json_request):
        """
        This is called after we make the connection with the protocol for this
        connection. The connection is established, so we send the (already
        encoded) request.

        @type protocol: t.i.p.Protocol
        @param protocol: Protocol that matches the new made connection

        @type json_request: str|unicode
        @param json_request: The already encoded request
        """

        protocol.sendString(json_request)

    def callRemote(self, method, *args, **kwargs):
        """
        Remotely calls the method, with args. Given that we keep reference to
        the call via the Deferred, there's no need for id. It will coin some
        random anyway, just to satisfy the spec.

        According to the spec, we cannot use either args and kwargs at once.
        If there are kwargs, they get used and args are ignored.


        @type method: str
        @param method: Method name

        @type *args: list
        @param *args: List of agruments for the method. It gets ignored if
            kwargs is not empty.

        @type **kwargs: dict
        @param **kwargs: Dict of positional arguments for the method

        @rtype: t.i.d.Deferred
        @return: Deferred, that will fire with whatever the 'method' returned.
        @TODO support batch requests
        """

        if kwargs:
            json_request = jsonrpc.encodeRequest(method, kwargs,
                                                 version=self.version)
        else:
            json_request = jsonrpc.encodeRequest(method, args,
                                                 version=self.version)

        if self.verbose:
            log.msg('Sending: %s' % json_request)

        response_deferred = ResponseDeferred(verbose=self.verbose)
        factory = CallbackFactory(response_deferred.responseReceived)
        point = TCP4ClientEndpoint(reactor, self.hostname, self.port,
                                   timeout=self.timeout)
        d = point.connect(factory)
        d.addCallback(self.connectionMade, json_request)

        # response_deferred will be fired in responseReceived, after
        # we got response from the RPC server
        response_deferred.addCallback(jsonrpc.decodeResponse)
        return response_deferred
