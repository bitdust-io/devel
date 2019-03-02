__package__="txrestapi"

from six import PY2, b

import txrestapi  # @UnresolvedImport
import re
import json
import base64
import os.path
import doctest

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.defer import inlineCallbacks
from twisted.web.resource import Resource, NoResource
from twisted.web.server import Request, Site
from twisted.web.client import getPage
from twisted.trial import unittest


from .resource import APIResource
from .json_resource import JsonAPIResource
from .methods import GET, PUT


class FakeChannel(object):
    transport = None

    def getPeer(self):
        return None

    def getHost(self):
        return None


def getRequest(method, url):
    req = Request(FakeChannel(), None)
    req.method = method
    req.path = url
    return req


class APIResourceTest(unittest.TestCase):

    test_class = APIResource

    def test_returns_normal_resources(self):
        r = self.test_class()
        a = Resource()
        r.putChild(b('a'), a)
        req = Request(FakeChannel(), None)
        a_ = r.getChild(b('a'), req)
        self.assertEqual(a, a_)

    def test_registry(self):
        compiled = re.compile(b('regex'))
        r = self.test_class()
        r.register(b('GET'), b('regex'), None)
        self.assertEqual([x[0] for x in r._registry], [b('GET')])
        self.assertEqual(r._registry[0][0], b('GET'))
        # This doesn't work:
        #     FailTest: <_sre.SRE_Pattern object at 0x1052f6990> != <_sre.SRE_Pattern object at 0x1052f6d78>
        # self.assertEqual(r._registry[0][1], compiled)
        self.assertEqual(r._registry[0][1].pattern, compiled.pattern)
        self.assertEqual(r._registry[0][2], None)

    def test_method_matching(self):
        r = self.test_class()
        r.register(b('GET'), b('regex'), 1)
        r.register(b('PUT'), b('regex'), 2)
        r.register(b('GET'), b('another'), 3)

        req = getRequest(b('GET'), b('regex'))
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 1)

        req = getRequest(b('PUT'), b('regex'))
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 2)

        req = getRequest(b('GET'), b('another'))
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 3)

        req = getRequest(b('PUT'), b('another'))
        result = r._get_callback(req)
        self.assertEqual(result, (None, None))

    def test_callback(self):
        marker = object()
        def cb(request):
            return marker
        r = self.test_class()
        r.register(b('GET'), b('regex'), cb)
        req = getRequest(b('GET'), b('regex'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(result.render(req), marker)

    def test_longerpath(self):
        marker = object()
        r = self.test_class()
        def cb(request):
            return marker
        r.register(b('GET'), b('/regex/a/b/c'), cb)
        req = getRequest(b('GET'), b('/regex/a/b/c'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(result.render(req), marker)

    def test_args(self):
        r = self.test_class()
        def cb(request, **kwargs):
            return kwargs
        r.register(b('GET'), b('/(?P<a>[^/]*)/a/(?P<b>[^/]*)/c'), cb)
        req = getRequest(b('GET'), b('/regex/a/b/c'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(sorted(result.render(req).keys()), ['a', 'b'])

    def test_order(self):
        r = self.test_class()
        def cb1(request, **kwargs):
            kwargs.update({'cb1':True})
            return kwargs
        def cb(request, **kwargs):
            return kwargs
        # Register two regexes that will match
        r.register(b('GET'), b('/(?P<a>[^/]*)/a/(?P<b>[^/]*)/c'), cb1)
        r.register(b('GET'), b('/(?P<a>[^/]*)/a/(?P<b>[^/]*)'), cb)
        req = getRequest(b('GET'), b('/regex/a/b/c'))
        result = r.getChild(b('regex'), req)
        # Make sure the first one got it
        self.assert_('cb1' in result.render(req))

    def test_no_resource(self):
        r = self.test_class()
        r.register(b('GET'), b('^/(?P<a>[^/]*)/a/(?P<b>[^/]*)$'), None)
        req = getRequest(b('GET'), b('/definitely/not/a/match'))
        result = r.getChild(b('regex'), req)
        self.assert_(isinstance(result, NoResource))

    def test_all(self):
        r = self.test_class()
        def get_cb(r): return b('GET')
        def put_cb(r): return b('PUT')
        def all_cb(r): return b('ALL')
        r.register(b('GET'), b('^path'), get_cb)
        r.register(b('ALL'), b('^path'), all_cb)
        r.register(b('PUT'), b('^path'), put_cb)
        # Test that the ALL registration picks it up before the PUT one
        for method in (b('GET'), b('PUT'), b('ALL')):
            req = getRequest(method, b('path'))
            result = r.getChild(b('path'), req)
            self.assertEqual(result.render(req), b('ALL') if method==b('PUT') else method)

 
class JSONAPIResourceTest(APIResourceTest):
 
    test_class = JsonAPIResource
 
    def test_all(self):
        r = self.test_class()
        def get_cb(r): return {'method': b('GET'), }
        def put_cb(r): return {'method': b('PUT'), }
        def all_cb(r): return {'method': b('ALL'), }
        r.register(b('GET'), b('^path'), get_cb)
        r.register(b('ALL'), b('^path'), all_cb)
        r.register(b('PUT'), b('^path'), put_cb)
        # Test that the ALL registration picks it up before the PUT one
        for method in (b('GET'), b('PUT'), b('ALL')):
            req = getRequest(method, b('path'))
            result = r.getChild(b('path'), req)
            self.assertEqual(json.loads(result.render(req))['method'], b('ALL') if method==b('PUT') else method)

    def test_args(self):
        r = self.test_class()
        def cb(request, **kwargs):
            return {'kwargs': kwargs, }
        r.register(b('GET'), b('/(?P<a>[^/]*)/a/(?P<b>[^/]*)/c'), cb)
        req = getRequest(b('GET'), b('/regex/a/b/c'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(sorted(json.loads(result.render(req))['kwargs'].keys()), ['a', 'b'])

    def test_callback(self):
        marker = base64.b64encode(os.urandom(20))
        def cb(request):
            return {'marker': marker, }
        r = self.test_class()
        r.register(b('GET'), b('regex'), cb)
        req = getRequest(b('GET'), b('regex'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(json.loads(result.render(req))['marker'], marker)

    def test_longerpath(self):
        marker = base64.b64encode(os.urandom(20))
        r = self.test_class()
        def cb(request):
            return {'marker': marker, }
        r.register(b('GET'), b('/regex/a/b/c'), cb)
        req = getRequest(b('GET'), b('/regex/a/b/c'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(json.loads(result.render(req))['marker'], marker)

    def test_no_resource(self):
        r = self.test_class()
        r.register(b('GET'), b('^/(?P<a>[^/]*)/a/(?P<b>[^/]*)$'), None)
        req = getRequest(b('GET'), b('/definitely/not/a/match'))
        result = r.getChild(b('regex'), req)
        self.assertEqual(json.loads(result.render(req))['errors'], ["path 'regex' not found", ])


class TestResource(Resource):
    isLeaf = True
    def render(self, request):
        return b('aresource')


class TestAPI(APIResource):

    @GET(b('^/(?P<a>test[^/]*)/?'))
    def _on_test_get(self, request, a):
        return b('GET %s') % a

    @PUT(b('^/(?P<a>test[^/]*)/?'))
    def _on_test_put(self, request, a):
        return b('PUT %s') % a

    @GET(b('^/gettest'))
    def _on_gettest(self, request):
        return TestResource()


class DecoratorsTest(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")  # @UndefinedVariable

    def setUp(self):
        r = TestAPI()
        site = Site(r, timeout=None)
        self.port = self._listen(site)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getURL(self, path):
        return b("http://127.0.0.1:%d/%s" % (self.portno, path))

    @inlineCallbacks
    def test_get(self):
        url = self.getURL('test_thing/')
        result = yield getPage(url, method=b('GET'))
        self.assertEqual(result, b('GET test_thing'))

    @inlineCallbacks
    def test_put(self):
        url = self.getURL('test_thing/')
        result = yield getPage(url, method=b('PUT'))
        self.assertEqual(result, b('PUT test_thing'))

    @inlineCallbacks
    def test_resource_wrapper(self):
        url = self.getURL('gettest')
        result = yield getPage(url, method=b('GET'))
        self.assertEqual(result, b('aresource'))


def test_suite():
    import unittest as ut
    suite = unittest.TestSuite()
    suite.addTest(ut.makeSuite(DecoratorsTest))
    suite.addTest(ut.makeSuite(APIResourceTest))
    if PY2:
        suite.addTest(doctest.DocFileSuite(os.path.join('..', 'README.rst')))
    return suite
