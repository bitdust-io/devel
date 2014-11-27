
from __future__ import nested_scopes

from twisted.internet import defer
import sys

class _DeferredCache:
    """ Wraps a call that returns a deferred in a cache. Any subsequent
        calls with the same argument will wait for the first call to
        finish and return the same result (or errback).
    """

    hashableArgs = False
    inProgressOnly = True

    def __init__(self, op, hashableArgs=None, inProgressOnly=None):
        self.op = op
        self.cache = {}
        if hashableArgs is not None:
            self.hashableArgs = hashableArgs
        if inProgressOnly is not None:
            self.inProgressOnly = inProgressOnly

    def cb_triggerUserCallback(self, res, deferred):
        #print "triggering", deferred
        deferred.callback(res)
        return res

    def cb_triggerUserErrback(self, failure, deferred):
        deferred.errback(failure)
        return failure

    def _genCache(self, args, kwargs):
        # This could be better, probably
        try:
            arghash = hash(args)
        except TypeError:
            return None
        kwit = kwargs.items()
        kwit.sort()
        try:
            kwhash = hash(tuple(kwit))
        except TypeError:
            return None
        return (arghash, kwhash)

    def _removeCacheVal(self, res, cacheVal):
        del self.cache[cacheVal]
        return res

    def clearCache(self):
        self.cache = {}

    def call(self, *args, **kwargs):
        # Currently not in progress - start it
        #print "called with", args
        cacheVal = self._genCache(args, kwargs)
        if cacheVal is None and self.hashableArgs:
            raise TypeError('DeferredCache(%s) arguments must be hashable'%(
                                self.op.func_name))

        opdef = self.cache.get(cacheVal)
        if not opdef:
            # XXX assert that it returns a deferred?
            opdef = self.op(*args, **kwargs)
            if cacheVal is not None:
                self.cache[cacheVal] = opdef
            if self.inProgressOnly and cacheVal:
                opdef.addCallbacks(lambda x: self._removeCacheVal(x, cacheVal),
                                   lambda x: self._removeCacheVal(x, cacheVal))

        userdef = defer.Deferred()
        opdef.addCallbacks(lambda x: self.cb_triggerUserCallback(x, userdef),
                           lambda x: self.cb_triggerUserErrback(x, userdef))
        return userdef


def DeferredCache(op=None, hashableArgs=None, inProgressOnly=None):
    """ Use this as a decorator for a function or method that returns a
        deferred. Any subsequent calls using the same arguments will
        be all triggered off the original deferred, all returning the
        same result.
    """
    if op is None:
        return lambda x: DeferredCache(x, hashableArgs, inProgressOnly)
    c = _DeferredCache(op, hashableArgs, inProgressOnly)
    def func(*args, **kwargs):
        return c.call(*args, **kwargs)
    if sys.version_info > (2,4):
        func.func_name = op.func_name
    func.clearCache = c.clearCache
    func.cache_hashableArgs = c.hashableArgs
    func.cache_inProgressOnly = c.inProgressOnly
    return func
