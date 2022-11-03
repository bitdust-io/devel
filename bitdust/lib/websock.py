#!/usr/bin/python
# websock.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (websock.py) is part of BitDust Software.
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
#
#
#
"""
..

module:: websock
"""

#------------------------------------------------------------------------------

import os
import time
import json
try:
    from queue import Queue, Empty
except:
    from Queue import Queue, Empty  # @UnresolvedImport

#------------------------------------------------------------------------------

from twisted.internet import reactor  # @UnresolvedImport

#------------------------------------------------------------------------------

from bitdust_forks import websocket

from bitdust.system import local_fs

#------------------------------------------------------------------------------

_Debug = False
_DebugAPIResponses = _Debug

#------------------------------------------------------------------------------

_APISecretFilePath = None
_WebSocketApp = None
_WebSocketQueue = None
_WebSocketReady = False
_WebSocketClosed = True
_WebSocketStarted = False
_WebSocketConnecting = False
_LastCallID = 0
_PendingCalls = []
_CallbacksQueue = {}
_RegisteredCallbacks = {}
_ResponseTimeoutTasks = {}

#------------------------------------------------------------------------------


def start(callbacks={}, api_secret_filepath=None):
    global _APISecretFilePath
    global _WebSocketStarted
    global _WebSocketConnecting
    global _WebSocketQueue
    global _RegisteredCallbacks
    if is_started():
        raise Exception('already started')
    if _Debug:
        print('websock.start()')
    _APISecretFilePath = api_secret_filepath
    _RegisteredCallbacks = callbacks or {}
    _WebSocketConnecting = True
    _WebSocketStarted = True
    _WebSocketQueue = Queue(maxsize=100)
    reactor.callInThread(websocket_thread)  # @UndefinedVariable
    reactor.callInThread(requests_thread, _WebSocketQueue)  # @UndefinedVariable


def stop():
    global _APISecretFilePath
    global _WebSocketStarted
    global _WebSocketQueue
    global _WebSocketConnecting
    global _RegisteredCallbacks
    if not is_started():
        raise Exception('has not been started')
    if _Debug:
        print('websock.stop()')
    _APISecretFilePath = None
    _RegisteredCallbacks = {}
    _WebSocketStarted = False
    _WebSocketConnecting = False
    while True:
        try:
            json_data, _, _, _ = ws_queue().get_nowait()
            if _Debug:
                print('cleaned unfinished call', json_data)
        except Empty:
            break
    _WebSocketQueue.put_nowait((
        None,
        None,
        None,
        None,
    ))
    if ws():
        if _Debug:
            print('websocket already closed')
        ws().close()


#------------------------------------------------------------------------------


def ws():
    global _WebSocketApp
    return _WebSocketApp


def ws_queue():
    global _WebSocketQueue
    return _WebSocketQueue


def is_ready():
    global _WebSocketReady
    return _WebSocketReady


def is_closed():
    global _WebSocketClosed
    return _WebSocketClosed


def is_started():
    global _WebSocketStarted
    return _WebSocketStarted


def is_connecting():
    global _WebSocketConnecting
    return _WebSocketConnecting


def registered_callbacks():
    global _RegisteredCallbacks
    return _RegisteredCallbacks


#------------------------------------------------------------------------------


def on_open(ws_inst):
    global _WebSocketReady
    global _WebSocketClosed
    global _WebSocketConnecting
    global _PendingCalls
    _WebSocketReady = True
    _WebSocketClosed = False
    _WebSocketConnecting = False
    if _Debug:
        print('websocket opened', time.time(), len(_PendingCalls))
    cb = registered_callbacks().get('on_open')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable
    for json_data, cb, tm, timeout in _PendingCalls:
        ws_queue().put_nowait((
            json_data,
            cb,
            tm,
            timeout,
        ))
    _PendingCalls.clear()


def on_close(ws_inst):
    global _WebSocketReady
    global _WebSocketClosed
    global _WebSocketConnecting
    _WebSocketReady = False
    _WebSocketClosed = True
    _WebSocketConnecting = False
    if _Debug:
        print('websocket closed', time.time())
    cb = registered_callbacks().get('on_close')
    if cb:
        reactor.callFromThread(cb, ws_inst)  # @UndefinedVariable


def on_event(json_data):
    if _Debug:
        print('    WS EVENT:', json_data['payload']['event_id'])
    cb = registered_callbacks().get('on_event')
    if cb:
        reactor.callFromThread(cb, json_data)  # @UndefinedVariable
    return True


def on_stream_message(json_data):
    if _Debug:
        print('    WS STREAM MSG:', json_data['payload']['payload']['message_id'])
    cb = registered_callbacks().get('on_stream_message')
    if cb:
        reactor.callFromThread(cb, json_data)  # @UndefinedVariable
    return True


def on_message(ws_inst, message):
    global _CallbacksQueue
    global _ResponseTimeoutTasks
    json_data = json.loads(message)
    if _Debug:
        print('        on_message %d bytes:' % len(message), message)
    if 'payload' not in json_data:
        if _Debug:
            print('        no payload found in the response')
        return False
    payload_type = json_data.get('type')
    if payload_type == 'event':
        return on_event(json_data)
    if payload_type == 'stream_message':
        return on_stream_message(json_data)
    if payload_type == 'api_call':
        if 'call_id' not in json_data['payload']:
            if _Debug:
                print('        call_id not found in the response')
            return
        call_id = json_data['payload']['call_id']
        timeout_task = _ResponseTimeoutTasks.pop(call_id, None)
        if timeout_task:
            if not timeout_task.called:
                timeout_task.cancel()
        if call_id not in _CallbacksQueue:
            if _Debug:
                print('        call_id found in the response, but no callbacks registered')
            return
        result_callback = _CallbacksQueue.pop(call_id, None)
        if _DebugAPIResponses:
            print('WS API Response {} : {}'.format(
                call_id,
                json_data['payload']['response'],
            ))
        if result_callback:
            reactor.callFromThread(result_callback, json_data)  # @UndefinedVariable
        return True
    if _Debug:
        print('        unexpected payload_type', json_data)
    raise Exception(payload_type)


def on_error(ws_inst, error):
    global _PendingCalls
    if _Debug:
        print('on_error', error)
    cb = registered_callbacks().get('on_error')
    if cb:
        reactor.callFromThread(cb, error)  # @UndefinedVariable


def on_fail(err, result_callback=None):
    if _Debug:
        print('on_fail', err)
    if result_callback:
        reactor.callFromThread(result_callback, err)  # @UndefinedVariable


def on_request_timeout(call_id):
    global _CallbacksQueue
    global _ResponseTimeoutTasks
    if _Debug:
        print('on_request_timeout', call_id)
    # timeout_task =
    _ResponseTimeoutTasks.pop(call_id, None)
    # if timeout_task:
    #     if not timeout_task.called:
    #         timeout_task.cancel()
    res_cb = _CallbacksQueue.pop(call_id, None)
    if _DebugAPIResponses:
        print('WS API Request TIMEOUT {}'.format(call_id))
    if res_cb:
        reactor.callFromThread(res_cb, Exception('request timeout'))  # @UndefinedVariable


#------------------------------------------------------------------------------


def requests_thread(active_queue):
    global _LastCallID
    global _CallbacksQueue
    global _ResponseTimeoutTasks
    if _Debug:
        print('\nrequests_thread() starting')
    while True:
        if not is_started():
            if _Debug:
                print('\nrequests_thread() finishing because web socket is not started')
            break
        json_data, result_callback, tm, timeout = active_queue.get()
        if json_data is None:
            if _Debug:
                print('\nrequests_thread() received empty request, about to stop the thread now')
            break
        if 'call_id' not in json_data:
            _LastCallID += 1
            json_data['call_id'] = _LastCallID
        else:
            _LastCallID = json_data['call_id']
        call_id = json_data['call_id']
        if call_id in _CallbacksQueue:
            on_fail(Exception('call_id was not unique'), result_callback)
            continue
        if not ws():
            on_fail(Exception('websocket is closed'), result_callback)
            continue
        _CallbacksQueue[call_id] = result_callback
        data = json.dumps(json_data)
        if _Debug:
            print('sending', data)
        ws().send(data)
        if timeout is not None:
            now = time.time()
            dt = now - tm + timeout
            if dt < 0:
                res_cb = _CallbacksQueue.pop(call_id, None)
                if _DebugAPIResponses:
                    print('\n    WS API Request already TIMED OUT {} : now={} tm={} timeout={}'.format(
                        call_id,
                        now,
                        tm,
                        timeout,
                    ))
                on_fail(Exception('request timeout'), res_cb)
            else:
                _ResponseTimeoutTasks[call_id] = reactor.callLater(dt, on_request_timeout, call_id)  # @UndefinedVariable
    if _Debug:
        print('\nrequests_thread() finished')


def websocket_thread():
    global _APISecretFilePath
    global _WebSocketApp
    global _WebSocketClosed
    websocket.enableTrace(False)
    while is_started():
        _WebSocketClosed = False
        ws_url = 'ws://localhost:8280/'
        if _APISecretFilePath:
            if os.path.isfile(_APISecretFilePath):
                api_secret = local_fs.ReadTextFile(_APISecretFilePath)
                if api_secret:
                    ws_url += '?api_secret=' + api_secret
        if _Debug:
            print('websocket_thread() ws_url=%r' % ws_url)
        _WebSocketApp = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        try:
            ws().run_forever(ping_interval=10)
        except Exception as exc:
            _WebSocketApp = None
            if _Debug:
                print('\n    WS Thread ERROR:', exc)
            time.sleep(1)
        if _WebSocketApp:
            del _WebSocketApp
            _WebSocketApp = None
        if not is_started():
            break
        time.sleep(1)
    _WebSocketApp = None


#------------------------------------------------------------------------------


def verify_state():
    global _WebSocketReady
    global _WebSocketConnecting
    if is_closed():
        _WebSocketReady = False
        if _Debug:
            print('WS CALL REFUSED, web socket already closed')
        if is_connecting():
            if _Debug:
                print('web socket closed but still connecting')
            return 'closed'
        return 'closed'
    if is_ready():
        return 'ready'
    if is_connecting():
        return 'connecting'
    if is_started():
        return 'connecting'
    return 'not-started'


#------------------------------------------------------------------------------


def ws_call(json_data, cb=None, timeout=None):
    global _PendingCalls
    st = verify_state()
    if _Debug:
        print('ws_call', st)
    if st == 'ready':
        ws_queue().put_nowait((
            json_data,
            cb,
            time.time(),
            timeout,
        ))
        return True
    if st == 'closed':
        if cb:
            cb(Exception('web socket is closed'))
        return False
    if st == 'connecting':
        if _Debug:
            print('web socket still connecting, remember pending request')
        _PendingCalls.append((
            json_data,
            cb,
            time.time(),
            timeout,
        ))
        return True
    if st == 'not-started':
        if _Debug:
            print('web socket was not started')
        if cb:
            cb(Exception('web socket was not started'))
        return False
    raise Exception('unexpected state %r' % st)
