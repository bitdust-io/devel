import re
import json
import time

from itertools import ifilter
from functools import wraps

from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import Deferred


def _to_json(output_object):
    return json.dumps(
        output_object,
        indent=2,
        separators=(',', ': '),
        sort_keys=True,
    ) + '\n'


class _JsonResource(Resource):
    _result = ''
    isLeaf = True

    def __init__(self, result, executed):
        Resource.__init__(self)
        self._result = result
        self._executed = executed

    def _setHeaders(self, request):
        request.responseHeaders.addRawHeader(b'content-type', b'application/json')
        request.responseHeaders.addRawHeader(b'Access-Control-Allow-Origin', b'*')
        request.responseHeaders.addRawHeader(b'Access-Control-Allow-Methods', b'GET, POST, PUT, DELETE')
        request.responseHeaders.addRawHeader(b'Access-Control-Allow-Headers', b'x-prototype-version,x-requested-with')
        request.responseHeaders.addRawHeader(b'Access-Control-Max-Age', 2520)
        return request

    def render(self, request):
        self._setHeaders(request)
        self._result['execution'] = '%3.6f' % (time.time() - self._executed)
        return _to_json(self._result)


class _DelayedJsonResource(_JsonResource):

    def _cb(self, result, request):
        self._setHeaders(request)
        result['execution'] = '%3.6f' % (time.time() - self._executed)
        request.write(_to_json(result))
        request.finish()

    def _eb(self, err, request):
        self._setHeaders(request)
        execution = '%3.6f' % (time.time() - self._executed)
        request.write(_to_json(dict(status='ERROR', execution=execution, errors=[str(err), ])))
        request.finish()

    def render(self, request):
        self._result.addCallback(self._cb, request)
        self._result.addErrback(self._eb, request)
        return NOT_DONE_YET


def maybeResource(f):
    @wraps(f)
    def inner(*args, **kwargs):
        _executed = time.time()
        try:
            result = f(*args, **kwargs)
        except Exception as exc:
            return _JsonResource(dict(status='ERROR', errors=[str(exc), ]), _executed)
        if isinstance(result, Deferred):
            return _DelayedJsonResource(result, _executed)
        if not isinstance(result, Resource):
            result = _JsonResource(result, _executed)
        return result
    return inner


class APIResource(Resource):

    _registry = None

    def __init__(self, *args, **kwargs):
        Resource.__init__(self, *args, **kwargs)
        self._registry = []

    def _get_callback(self, request):
        filterf = lambda t: t[0] in (request.method, 'ALL')
        path_to_check = getattr(request, '_remaining_path', request.path)
        for _, r, cb in ifilter(filterf, self._registry):
            result = r.search(path_to_check)
            if result:
                request._remaining_path = path_to_check[result.span()[1]:]
                return cb, result.groupdict()
        return None, None

    def register(self, method, regex, callback):
        self._registry.append((method, re.compile(regex), callback))

    def unregister(self, method=None, regex=None, callback=None):
        if regex is not None:
            regex = re.compile(regex)
        for m, r, cb in self._registry[:]:
            if not method or (method and m == method):
                if not regex or (regex and r == regex):
                    if not callback or (callback and cb == callback):
                        self._registry.remove((m, r, cb))

    def getChild(self, name, request):
        r = self.children.get(name, None)
        if r is None:
            # Go into the thing
            callback, args = self._get_callback(request)
            if callback is None:
                return _JsonResource(dict(status='ERROR', errors=['path \'%s\' not found' % name, ]), time.time())
            else:
                return maybeResource(callback)(request, **args)
        else:
            return r
