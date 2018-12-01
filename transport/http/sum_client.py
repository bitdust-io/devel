


# Save this in to a file sum_client.py

from __future__ import absolute_import
from __future__ import print_function
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.protocol import ClientCreator
from twisted.protocols import amp

class Sum(amp.Command):
    # normally shared by client and server code
    arguments = [(b'a', amp.Integer()),
                 (b'b', amp.Integer())]
    response = [(b'total', amp.Integer())]

def connected(protocol):
    return protocol.callRemote(Sum, a=10, b=81
        ).addCallback(gotResult)

def gotResult(result):
    print(('total: %d' % (result['total'],)))
    reactor.stop()

def error(reason):
    print("Something went wrong")
    print(reason)
    reactor.stop()

ClientCreator(reactor, amp.AMP).connectTCP(
    '127.0.0.1', 1234).addCallback(connected).addErrback(error)

reactor.run()
