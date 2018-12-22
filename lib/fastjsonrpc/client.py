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
JSONRPC Client
==============

Provides a Proxy class, that can be used for calling remote functions via
JSON-RPC.
"""

from __future__ import absolute_import
import base64

# from zope.interface import implements
from zope.interface import implementer
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer

from twisted.cred.credentials import Anonymous, UsernamePassword
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred
from twisted.web.client import (Agent, ContentDecoderAgent, GzipDecoder,
                                HTTPConnectionPool)
from twisted.web.http_headers import Headers

from . import jsonrpc


class ReceiverProtocol(Protocol):
    """
    Protocol for receiving the server response.

    It's only purpose is to get the HTTP request body. Instance of this
    will be passed to the Response's deliverBody method.
    """

    def __init__(self, finished):
        """
        @type finished: t.i.d.Deferred
        @param finished: Deferred to be called when we've got all the data.
        """

        self.body = b''
        self.finished = finished

    def dataReceived(self, data):
        """
        Appends data to the internal buffer.

        @type data: str (bytearray, buffer?)
        @param data: Data from server. 'Should' be (a part of) JSON
        """

        self.body += data

    def connectionLost(self, reason):
        """
        Fires the finished's callback with data we've received.

        @type reason: t.p.f.Failure
        @param reason: Failure, wrapping several potential reasons. It can
        wrap t.w.c.ResponseDone, in which case everything is OK. It can wrap
        t.w.h.PotentialDataLoss. Or it can wrap an Exception, in case of an
        error.

        @TODO inspect reason for failures
        """

        self.finished.callback(self.body)


@implementer(IBodyProducer)
class StringProducer(object):
    """
    There's no FileBodyProducer in Twisted < 12.0.0 See
    http://twistedmatrix.com/documents/current/web/howto/client.html for
    details about this class.
    """
    # implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class ProxyFactory(object):
    """
    A factory to create Proxy objects.

    Passed parameters are used to create all proxies. Supports creating
    proxies with a connection pool shared between them.
    """

    def __init__(self, **kwargs):
        """
        @type version: int
        @param version: Which JSON-RPC version to use? The default is 1.0.

        @type connectTimeout: float
        @param connectTimeout: Connection timeout. Note that we don't connect
            when creating this object, but in callRemote, so the timeout
            will apply to callRemote.

        @type credentials: twisted.cred.credentials.ICredentials
        @param credentials: Credentials for basic HTTP authentication.
            Supported are Anonymous and UsernamePassword classes.
            If None then t.c.c.Anonymous object is used as default.

        @type contextFactory: twisted.internet.ssl.ClientContextFactory
        @param contextFactory: A context factory for SSL clients.
            If None then Agent's default is used.

        @type persistent: bool
        @param persistent: Boolean indicating whether connections should be
            persistent. If None then no persistent connections are created
            (default behavior of t.w.c.Agent class).

        @type maxPersistentPerHost: int
        @param maxPersistentPerHost: The maximum number of cached persistent
            connections for a host:port destination.

        @type cachedConnectionTimeout: int
        @param cachedConnectionTimeout: Number of seconds a cached persistent
            connection will stay open before disconnecting.

        @type retryAutomatically: bool
        @param retryAutomatically: Boolean indicating whether idempotent
            requests should be retried once if no response was received.

        @type compressedHTTP: bool
        @param compressedHTTP: Boolean indicating whether proxies can support
            HTTP compression (actually gzip).

        @type sharedPool: bool
        @type sharedPool: Share one connection pool between all created proxies.
            The default is False.
        """
        self._version = kwargs.get('version') or jsonrpc.VERSION_1
        self._connectTimeout = kwargs.get('connectTimeout')
        self._credentials = kwargs.get('credentials')
        self._contextFactory = kwargs.get('contextFactory')
        self._persistent = kwargs.get('persistent') or False
        self._maxPersistentPerHost = kwargs.get('maxPersistentPerHost')
        if self._maxPersistentPerHost is None:
            self._maxPersistentPerHost = HTTPConnectionPool.maxPersistentPerHost
        self._cachedConnectionTimeout = kwargs.get('cachedConnectionTimeout')
        if self._cachedConnectionTimeout is None:
            self._cachedConnectionTimeout = HTTPConnectionPool.cachedConnectionTimeout
        self._retryAutomatically = kwargs.get('retryAutomatically')
        if self._retryAutomatically is None:
            self._retryAutomatically = HTTPConnectionPool.retryAutomatically
        self._compressedHTTP = kwargs.get('compressedHTTP') or False
        self._sharedPool = kwargs.get('sharedPool') or False

        self._pool = None

        if self._sharedPool:
            self._pool = self._getConnectionPool()

    def getProxy(self, url):
        """
        Create a Proxy object by parameters passed to the factory.

        @type url: str
        @param url: URL of the RPC server. Supports HTTP and HTTPS for now,
            more might come in the future.

        @rtype: Proxy
        @return: Newly created Proxy object.
        """
        pool = None
        if self._sharedPool:
            pool = self._pool
        elif self._persistent:
            pool = self._getConnectionPool()

        kwargs = {'version': self._version,
                  'connectTimeout': self._connectTimeout,
                  'credentials': self._credentials,
                  'contextFactory': self._contextFactory,
                  'pool': pool}

        proxy = Proxy(url, **kwargs)

        if self._compressedHTTP:
            self._setContentDecoder(proxy)

        return proxy

    def _getConnectionPool(self):
        pool = HTTPConnectionPool(reactor, self._persistent)

        if self._persistent:
            pool.maxPersistentPerHost = self._maxPersistentPerHost
            pool.cachedConnectionTimeout = self._cachedConnectionTimeout
            pool.retryAutomatically = self._retryAutomatically

        return pool

    def _setContentDecoder(self, proxy):
        proxy.agent = ContentDecoderAgent(proxy.agent, [('gzip', GzipDecoder)])


class Proxy(object):
    """
    A proxy to one specific JSON-RPC server.

    Pass the server URL to the constructor and call
    proxy.callRemote('method', *args) to call 'method' with *args.
    """

    def __init__(self, url, version=jsonrpc.VERSION_1, connectTimeout=None,
                 credentials=None, contextFactory=None, pool=None):
        """
        @type url: str
        @param url: URL of the RPC server. Supports HTTP and HTTPS for now,
        more might come in the future.

        @type version: int
        @param version: Which JSON-RPC version to use? The default is 1.0.

        @type connectTimeout: float
        @param connectTimeout: Connection timeout. Note that we don't connect
            when creating this object, but in callRemote, so the timeout
            will apply to callRemote.

        @type credentials: twisted.cred.credentials.ICredentials
        @param credentials: Credentials for basic HTTP authentication.
            Supported are Anonymous and UsernamePassword classes.
            If None then t.c.c.Anonymous object is used as default.

        @type contextFactory: twisted.internet.ssl.ClientContextFactory
        @param contextFactory: A context factory for SSL clients.
            If None then Agent's default is used.

        @type pool: twisted.web.client.HTTPConnectionPool
        @param pool: Connection pool used to manage HTTP connections.
            If None then Agent's default is used.
        """

        self.url = url
        self.version = version

        if not credentials:
            credentials = Anonymous()

        if not isinstance(credentials, (Anonymous, UsernamePassword)):
            raise NotImplementedError(
                "'%s' credentials are not supported" % type(credentials))

        kwargs = {}

        if connectTimeout:
            kwargs['connectTimeout'] = connectTimeout

        if contextFactory:
            kwargs['contextFactory'] = contextFactory

        if pool:
            kwargs['pool'] = pool

        self.agent = Agent(reactor, **kwargs)
        self.credentials = credentials
        self.auth_headers = None

    def checkAuthError(self, response):
        """
        Check for authentication error.

        @type response: t.w.c.Response
        @param response: Response object from the call

        @raise JSONRPCError: If the call failed with authorization error

        @rtype: t.w.c.Response
        @return If there was no error, just return the response
        """

        if response.code == 401:
            raise jsonrpc.JSONRPCError('Unauthorized', jsonrpc.INVALID_REQUEST)
        return response

    def bodyFromResponse(self, response):
        """
        Parses out the body from the response.

        @type response: t.w.c.Response
        @param response: Response object from the call

        @rtype: t.i.d.Deferred
        @return: Deferred, that will fire callback with body of the response
            (as string)
        """

        finished = Deferred()
        response.deliverBody(ReceiverProtocol(finished))
        return finished

    def callRemote(self, method, *args, **kwargs):
        """
        Remotely calls the method, with args. Given that we keep reference to
        the call via the Deferred, there's no need for id. It will coin some
        random anyway, just to satisfy the spec.

        @type method: str
        @param method: Method name

        @type *args: list
        @param *args: List of agruments for the method.

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

        body = StringProducer(json_request.encode())

        headers_dict = {b'Content-Type': [b'application/json']}
        if not isinstance(self.credentials, Anonymous):
            headers_dict.update(self._getBasicHTTPAuthHeaders())
        headers = Headers(headers_dict)

        d = self.agent.request(b'POST', self.url, headers, body)
        d.addCallback(self.checkAuthError)
        d.addCallback(self.bodyFromResponse)
        d.addCallback(jsonrpc.decodeResponse)
        return d

    def _getBasicHTTPAuthHeaders(self):
        """
        @rtype dict
        @return 'Authorization' header
        """

        if not self.auth_headers:
            username = self.credentials.username
            password = self.credentials.password
            if password is None:
                password = ''

            encoded_cred = base64.encodestring(b'%s:%s' % (username, password))
            auth_value = b"Basic " + encoded_cred.strip()
            self.auth_headers = {b'Authorization': [auth_value]}

        return self.auth_headers
