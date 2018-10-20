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
import six

from twisted.web import resource
from twisted.web import server
from twisted.internet.defer import maybeDeferred
from twisted.internet.defer import DeferredList
from twisted.internet.defer import succeed

from . import jsonrpc


class JSONRPCServer(resource.Resource):
    """
    JSON-RPC server. Subclass this, implement your own methods and publish this
    as t.w.r.Resource using t.w.s.Site.

    It will expose all methods that start with 'jsonrpc_' (without the
    'jsonrpc_' part).
    """

    isLeaf = 1

    def _getRequestContent(self, request):
        """
        Parse the JSON from the request. Return it as a list, even if there was
        only one method call (which would give us a dict). This will be useful
        later, as we can iterate over it in the same manner if it is a single
        call or a batch request.

        @type request: t.w.s.Request
        @param request: The request from client

        @rtype: list
        @return: List of dicts, one dict per method call.

        @raise JSONRPCError: If there's error in parsing.
        """

        request.content.seek(0, 0)
        request_json = request.content.read()
        request_content = jsonrpc.decodeRequest(request_json)

        return request_content

    def _parseError(self, request):
        """
        Coin a 'parse error' response and finish the request.

        @type request: t.w.s.Request
        @param request: Request from client
        """

        response = jsonrpc.parseError()
        self._sendResponse(response, request)

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

    def render(self, request):
        """
        This is the 'main' RPC method. This will always be called when a
        request arrives and it's up to this method to parse the request and
        dispatch it further.

        @type request: t.w.s.Request
        @param request: Request from client

        @rtype: some constant :-)
        @return: NOT_DONE_YET signalizing, that there's Deferred, that will
            take care about sending the response.

        @TODO verbose mode
        """

        try:
            request_content = self._getRequestContent(request)
        except jsonrpc.JSONRPCError:
            self._parseError(request)
            return server.NOT_DONE_YET

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
        dl.addBoth(self._cbFinishRequest, request, is_batch)

        return server.NOT_DONE_YET

    def _cbFinishRequest(self, results, request, is_batch):
        """
        Manages sending the response to the client and finishing the request.
        This gets called after all methods have returned.

        @type results: list
        @param results: List of tuples (success, result) what DeferredList
            returned.

        @type request: t.w.s.Request
        @param request: The request that came from a client

        @TODO: document is_batch
        """

        method_responses = []
        for (success, result) in results:
            if result is not None:
                method_responses.append(result)
        if not is_batch and len(method_responses) == 1:
            method_responses = method_responses[0]
        response = jsonrpc.prepareCallResponse(method_responses)
        if not isinstance(response, six.binary_type):
            response = response.encode(encoding='utf-8')
        self._sendResponse(response, request)

    def _sendResponse(self, response, request):
        """
        Send the response back to client. Expects it to be already serialized
        into JSON.

        @type response: str
        @param response: JSON with the response

        @type request: t.w.s.Request
        @param request The request that came from a client
        """

        if response != '[]':
            # '[]' is result of batch request with notifications only
            request.setHeader('Content-Type', 'application/json')
            request.setHeader('Content-Length', str(len(response)))
            request.write(response)

        request.finish()


def EncodingJSONRPCServer(server):
    """
    Return wrapped JSON-RPC server that supports HTTP compression (currently
    gzip).

    @type server: t.w.r.Resource
    @param server: Instance of JSONRPCServer

    @rtype: t.w.r.EncodingResourceWrapper
    @return: Wrapper that implements HTTP compression
    """
    from twisted.web.resource import EncodingResourceWrapper
    from twisted.web.server import GzipEncoderFactory

    return EncodingResourceWrapper(server, [GzipEncoderFactory()])
