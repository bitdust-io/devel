
# Server implementation for a "Sum" command which adds two integers
from __future__ import absolute_import
from twisted.protocols import amp
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.protocol import Factory

class Sum(amp.Command):
    # normally shared by client and server code
    arguments = [(b'a', amp.Integer()),
                 (b'b', amp.Integer())]
    response = [(b'total', amp.Integer())]

class Protocol(amp.AMP):
    @Sum.responder
    def sum(self, a, b):
        return {'total': a+b}

pf = Factory()
pf.protocol = Protocol
reactor.listenTCP(1234, pf) # listen on port 1234
reactor.run()

