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


================
JSON-RPC library
================

Provides functions for encoding and decoding the JSON into functions, params
etc. and other JSON-RPC related stuff like constants.
"""

from __future__ import absolute_import
import six

cjson_loaded = False
try:
    import cjson
    cjson_loaded = True
except ImportError:
    try:
        import json
    except ImportError:
        try:
            import simplejson as json
        except ImportError:
            raise ImportError('cjson, json or simplejson required')

import random
import types
from twisted.python.failure import Failure

VERSION_1 = 1.0
VERSION_2 = 2.0

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

ID_MIN = 1
ID_MAX = 2 ** 31 - 1  # 32-bit maxint


def jdumps(obj):
    """
    Encode JSON no matter what library did we import.

    @type obj: mixed
    @param obj: Whatever we want to encode

    @rtype: str
    @return: JSON representation of obj
    """

    def _to_text(v):
        if isinstance(v, six.binary_type):
            v = v.decode('utf-8')
        return v

    if cjson_loaded:
        try:
            return cjson.encode(obj)
        except cjson.EncodeError as e:
            raise ValueError(str(e))
    else:
        return json.dumps(obj, default=_to_text)


def jloads(json_string):
    """
    Decode JSON no matter what library did we import.

    @type json_string: str
    @param json_string: JSON to be decoded

    @rtype: mixed
    @return: Whatever the JSON contained
    """
    if cjson_loaded:
        try:
            return cjson.decode(json_string)
        except cjson.DecodeError as e:
            raise ValueError(str(e))
    else:
        return json.loads(json_string)


def encodeRequest(method, args=None, id_=0, version=VERSION_1):
    """
    Return a JSON object representation of the request.

    @type id_: int or None
    @param id_: request ID. If None, a notification will be sent. If 0 (the
        default), we'll coin some random.

    @type method: str
    @param method: Method name

    @type args: list
    @param args: List of arguments for the method. Note that packing of the
        arguments is up to the caller!

    @type version: float
    @param version: Which JSON-RPC version to use? Defaults to version 1.

    @rtype: str
    @return: JSON representation of the request
    @TODO support batch requests
    """

    request = {}
    request['method'] = method

    if args is not None:
        request['params'] = args

    if id_ is not None:
        if id_ == 0:
            id_ = random.randint(ID_MIN, ID_MAX)
        request['id'] = id_

    if version == VERSION_2:
        request['jsonrpc'] = '2.0'

    return jdumps(request)


def decodeResponse(json_response):
    """
    Parse the response JSON and return what the called function returned. Raise
    an exception in the case there was an error.

    @type json_response: str
    @param json_response: JSON from the server

    @rtype: mixed
    @return: What the function returned

    @raise ValueError: If the response is not valid JSON-RPC response.
    @TODO support batch requests
    """

    response = jloads(json_response)

    if 'jsonrpc' in response and response['jsonrpc'] == "2.0":
        if 'result' in response and 'error' in response:
            raise ValueError('Not a valid JSON-RPC response')
    else:
        if ('result' in response and response['result'] is not None and
                'error' in response and response['error'] is not None):
            raise ValueError('Not a valid JSON-RPC response')

    if 'error' in response and response['error'] is not None:
        e = JSONRPCError(response['error']['message'],
                         response['error']['code'])
        if 'jsonrpc' in response:
            e.version = response['jsonrpc']
        if 'id' in response:
            e.id_ = response['id']
        else:
            e.id_ = VERSION_1

        raise e

    if 'result' in response:
        return response['result']

    raise ValueError('Not a valid JSON-RPC response')


def decodeRequest(request):
    """
    Decodes the JSON encoded request.

    @type request: str
    @param request: The JSON encoded request

    @rtype: mixed
    @return: Whatever the client sent, most probably a list (in the case of
        a batch request) or dict (in the case of a single method call).

    @raise JSONRPCError: If there's error in parsing.
    @TODO if cjson_loaded catch cjson.DecodeError
    """

    try:
        decoded = jloads(request)
    except ValueError:
        raise JSONRPCError('Failed to parse JSON', PARSE_ERROR)

    return decoded


def verifyMethodCall(request):
    """
    Verifies a single method call. We call this for every method in case of a
    batch request. If there are any params missing and we don't need it, add
    it.

    @type request: dict
    @param request: Decoded request from user

    @rtype: dict
    @return: What we got, possibly with some keys more.

    @raise JSONRPCError: If there's anything wrong with the request, raise
    JSONRPCError with description of what's wrong. Attempts to add to it
        as much information as possible (id, version).
    """
    try:
        # 'jsonrpc' is only contained in V2 requests
        if 'jsonrpc' in request:
            if not isinstance(request['jsonrpc'],
                              ((str,), float)):
                raise JSONRPCError('Invalid jsonrpc type', INVALID_REQUEST)

            request['jsonrpc'] = float(request['jsonrpc'])
        else:
            request['jsonrpc'] = VERSION_1

        if 'id' not in request:
            request['id'] = None

        if (not 'method' in request or
                not isinstance(request['method'], (six.string_types,))):
            raise JSONRPCError('Invalid method type', INVALID_REQUEST)

        if ('params' in request and
                not isinstance(request['params'],
                               (list, tuple,
                                dict))):
            raise JSONRPCError('Invalid params type', INVALID_REQUEST)

        return request

    except JSONRPCError as e:
        # Add all known info to the exception, so we can return it correctly

        if 'id' in request and 'jsonrpc' in request:
            raise JSONRPCError(e.strerror, e.errno, id_=request['id'],
                               version=request['jsonrpc'])
        elif 'id' in request:
            raise JSONRPCError(e.strerror, e.errno, id_=request['id'])
        elif 'jsonrpc' in request:
            raise JSONRPCError(e.strerror, e.errno, version=request['jsonrpc'])
        else:
            raise JSONRPCError(e.strerror, e.errno)


def _getErrorResponse(exception):
    """
    Parses Exception into a dict, that can be encoded to JSON.

    @type result: Exception
    @param result: Exception to be parsed

    @rtype: dict
    @return: dict that can be serialized to JSON
    """

    error_result = {}
    try:
        error_result['message'] = str(exception.strerror)
    except AttributeError:
        error_result['message'] = str(exception)

    if isinstance(exception, TypeError):
        error_result['code'] = INVALID_PARAMS
    else:
        try:
            error_result['code'] = exception.errno
        except AttributeError:
            error_result['code'] = INTERNAL_ERROR

    try:
        if exception.data is not None:
            error_result['data'] = exception.data
    except AttributeError:
        pass

    return error_result


def prepareMethodResponse(result, id_=None, version=VERSION_1):
    """
    Add all info we have to the response, prepare it to be serialized.

    @type result: mixed
    @param result: What the called function returned. Might be a Failure!

    @type id_: int
    @param id_: the request id

    @type version: float
    @param version: JSON-RPC version

    @rtype: str
    @return: JSON-encoded response
    """
    
    if id_ is None:
        # notification
        return None

    if isinstance(result, Failure):
        result = result.value

    if isinstance(result, Exception):
        error_result = _getErrorResponse(result)
    else:
        error_result = None

    response = {}
    response['id'] = id_

    if version == VERSION_2:
        response['jsonrpc'] = "2.0"

    if error_result:
        response['error'] = error_result
        if version == VERSION_1:
            response['result'] = None
    else:
        response['result'] = result
        if version == VERSION_1:
            response['error'] = None

    return response


def prepareCallResponse(result):
    """
    Prepare the response to the 'whole' call, be it a single method or a batch
    request.

    @type result: mixed
    @param result: What we want to return to the client

    @rtype: str
    @return: Serialized result
    """
    return jdumps(result)


def parseError():
    """
    Coin 'parse error' response. Since we don't know id, default to NULL. And
    since we don't know jsonrpc version, default to '2.0', given that V1 spec
    doesn't cover parse errors.

    @rtype: str
    @return: Serialized message informing that there was a parse error.
    """
    response = {'jsonrpc': '2.0', 'id': None, 'error':
                {'code': PARSE_ERROR, 'message': 'Parse error'}}
    return jdumps(response)


class JSONRPCError(Exception):
    """
    JSON-RPC specific error.

    @TODO str, repr etc.?
    """

    def __init__(self, strerror, errno=INTERNAL_ERROR, data=None, id_=None,
                 version=VERSION_1):
        """
        @type strerror: str
        @param strerror: Description of the error

        @type errno: int
        @param errno: Error code

        @type data: mixed
        @param data: Whatever additional data we want to pass
        """
        self.strerror = strerror
        self.errno = errno
        self.data = data
        self.id_ = id_
        self.version = version

        Exception.__init__(self, strerror)
