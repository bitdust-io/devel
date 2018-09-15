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
from twisted.internet.defer import succeed, DeferredList, maybeDeferred
from twisted.python import log

from . import jsonrpc


class JSONRPCServer(basic.NetstringReceiver):

    def __init__(self, verbose=False):
        """
        Set verbosity level. By default we only log IP version, IP address and
        port of incoming request. With verbose=True, we log incoming requests
        bodies and outgoing responses bodies.

        @type verbose: bool
        @param verbose: Log details or not
        """

        self.verbose = verbose

    def _parseError(self):
        """
        Coin a 'parse error' response and finish the request.
        """

        response = jsonrpc.parseError()
        self._sendResponse(response)

    def _callMethod(self, request_dict):
        """
        Here we actually find and call the method.

        @type request_dict: dict
        @param request_dict: Dict with details about the method

        @rtype: Deferred
        @return: Deferred, that will eventually fire with the method's result.

        @raise JSONRPCError: When method not found.
        """

        function = getattr(self, 'jsonrpc_%s' % request_dict['method'], None)
        if callable(function):

            if 'params' in request_dict:
                if isinstance(request_dict['params'], dict):
                    d = maybeDeferred(function, **request_dict['params'])
                else:
                    d = maybeDeferred(function, *request_dict['params'])
            else:
                d = maybeDeferred(function)

            return d

        else:
            msg = 'Method %s not found' % request_dict['method']
            raise jsonrpc.JSONRPCError(msg, jsonrpc.METHOD_NOT_FOUND,
                                       id_=request_dict['id'],
                                       version=request_dict['jsonrpc'])

    def _logRequest(self, request):
        """
        Log incoming request.

        @type request: string|unicode
        @param request: The incoming request
        """

        log.msg('Incoming request from peer: %s' % self.transport.getPeer())
        if self.verbose:
            log.msg('Incoming request body: %s' % request)

    def stringReceived(self, string):
        """
        This is the 'main' RPC method. This will always be called when a
        request arrives and it's up to this method to parse the request and
        dispatch it further.

        @type string: str
        @param string: Request from client, just the 'string' itself, already
            stripped of the netstring stuff.

        @rtype: DeferredList
        @return: Deferred, that will fire when all methods are finished. It
            will already have all the callbacks and errbacks neccessary to
            finish and send the response.
        """

        self._logRequest(string)
        try:
            request_content = jsonrpc.decodeRequest(string)
        except jsonrpc.JSONRPCError:
            self._parseError()
            return None

        is_batch = True
        if not isinstance(request_content, list):
            request_content = [request_content]
            is_batch = False

        dl = []
        for request_dict in request_content:
            d = succeed(request_dict)
            d.addCallback(jsonrpc.verifyMethodCall)
            d.addCallback(self._callMethod)
            d.addBoth(jsonrpc.prepareMethodResponse, request_dict['id'],
                      request_dict['jsonrpc'])
            dl.append(d)

        dl = DeferredList(dl, consumeErrors=True)
        dl.addBoth(self._cbFinishRequest, is_batch)

        return dl

    def _cbFinishRequest(self, results, is_batch):
        """
        Manages sending the response to the client and finishing the request.
        This gets called after all methods have returned.

        @type results: list
        @param results: List of tuples (success, result) what DeferredList
            returned.

        @type is_batch: bool
        @param is_batch: True if the request was a batch, False if it wasn't
        """

        method_responses = []
        for (success, result) in results:
            if result is not None:
                method_responses.append(result)

        if not is_batch and len(method_responses) == 1:
            method_responses = method_responses[0]

        response = jsonrpc.prepareCallResponse(method_responses)
        self._sendResponse(response)

    def _logResponse(self, response):
        """
        Log the response - if appropriate verbosity level is set.

        @type response: str|unicode
        @param response: The JSON-encoded response we are about to send
        """

        if self.verbose:
            log.msg('Outgoing response: %s' % response)

    def _sendResponse(self, response):
        """
        Send the response to the client and close the connection.

        @type response: str|unicode
        @param response: The JSON-encoded response to send
        """

        if response != '[]':
            # '[]' is result of a notification, or a batch with notifications
            # only
            self._logResponse(response)
            self.sendString(response)

        self.transport.loseConnection()
