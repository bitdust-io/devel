#!/usr/bin/python
#server.py

import os
import sys
import codecs
import locale
import hashlib


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in upload_server.py')


from twisted.internet import task
from twisted.internet import protocol
from twisted.internet.protocol import ServerFactory, ClientFactory
from twisted.protocols import basic
from twisted.internet.defer import Deferred
from twisted.python import log


_DestinationDir = '/tmp'
_TrustedIPs = []

#-------------------------------------------------------------------------------

def init():
    global _DestinationDir
    global _TrustedIPs
    _DestinationDir = os.path.abspath(sys.argv[1])
    try:
        _TrustedIPs = open('trusted-ip-list').read().splitlines()
    except:
        _TrustedIPs = ['127.0.0.1']
    prnt(0, 'trusted IPs:')
    prnt(0, '\n'.join(_TrustedIPs))

#------------------------------------------------------------------------------ 

def read_binary_file(filename):
    if not os.path.isfile(filename):
        return ''
    if not os.access(filename, os.R_OK):
        return ''
    try:
        file = open(filename,"rb")
        data = file.read()
        file.close()
        # For binary data we can't play with \r\n to \n stuff
        return data
    except:
        return ''

def list_dir_recursive(dir):
    r = []
    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        if os.path.isdir(full_name):
            r.extend(list_dir_recursive(full_name))
        else:
            r.append(full_name)
    return r

def prnt(offs, str, new_line='\n'):
    #sys.stdout.write(unicode(' ' * offs + str + new_line).encode(sys.stdout.encoding))
    sys.stdout.write(' ' * offs + str + new_line)
    
def get_hash(src):
    return hashlib.md5(src).hexdigest()

def file_hash(path):
    src = read_binary_file(path)
    if not src:
        return None
    return get_hash(src)    

#------------------------------------------------------------------------------ 

class ReceiveFiles(protocol.Protocol):
    filename = ''
    filepath = ''
    length = 0
    length_gzipped = 0
    fout = None
    peer = ''
    received = 0
    blocks10K = 0
    buf = ''
    def connectionMade(self):
        if self.peer == "":
            self.peer = self.transport.getPeer()
            prnt(4, 'connection made with ' + str(self.peer))
        else:
            if self.peer != self.transport.getPeer():
                prnt(1, "NETERROR thought we had one object per connection")

    def parseData(self, data):
        self.buf += data
        while True:
            try:
                fname, fhash, length, length_gzipped, self.buf = self.buf.split('\n', 4)
                self.processFile(fname, fhash, length, length_gzipped)
            except:
                break

    def processFile(self, fname, fhash, length, length_gzipped):
        global _DestinationDir
        fpath = os.path.abspath(os.path.join(_DestinationDir, fname))
        if length == '?':
            self.transport.write(fname + '\n')
            if os.path.isfile(fpath):
                if file_hash(fpath) == fhash:
                    self.transport.write('equal\n')
                else:
                    self.transport.write('different\n')
            else:
                self.transport.write('noexist\n')
            return

        self.filename = fname
        self.filepath = fpath
        self.length = int(length)
        self.length_gzipped = int(length_gzipped)

        if os.path.isfile(self.filepath):
            if file_hash(self.filepath) == fhash:
                prnt(4, "[skip] %s" % self.filename)
                self.transport.write('%s\ndone\n' % self.filename)
                self.filename = ''
                self.filepath = ''
                self.length = 0
                self.length_gzipped = 0
                return
            else:
                self.transport.write('%s\nready\n' % self.filename)

        else:
            if not os.path.isdir(os.path.dirname(self.filepath)):
                prnt(4, "[make dir] " + os.path.dirname(self.filepath))
                os.makedirs(os.path.dirname(self.filepath))
            self.transport.write('%s\nready\n' % self.filename)

        self.fout = open(self.filepath+'.gz', 'wb')
        self.fout.write(self.buf)
        self.buf = ''

    def writeData(self, data):
        self.fout.write(data)
        amount = len(data)
        self.received += amount
        if self.received == self.length_gzipped:
            self.transport.write('%s\ndone\n' % self.filename)
            self.fout.close()
            os.system('gzip -d -f ' + self.filepath + '.gz')
            prnt(4, "[done] " + self.filename)
            self.filename = ''
            self.filepath = ''
            self.length = 0
            self.length_gzipped = 0
            self.received = 0
            #self.percent = 0
            self.blocks10K = 0
        else:
#            if self.length_gzipped != 0:
#                ratio = float(self.received) / float(self.length_gzipped)
#            else:
#                ratio = 1.0
#            newpercent = int(ratio * 10.0)
#            if newpercent != self.percent:
#                self.transport.write('%s\n%d\n' % (self.filename, int(self.percent)))
#            self.percent = newpercent
            curblocks10K = int(self.received / (10.0 * 1024.0))            
            if curblocks10K != self.blocks10K:
                self.transport.write('%s\n%d\n' % (self.filename, int(self.received)))
            self.blocks10K = curblocks10K


    def dataReceived(self, data):
        if self.filename == '':
            self.parseData(data)
        else:
            self.writeData(data)

    def connectionLost(self, reason):
        prnt(4, "connection lost with " + str(self.peer))


class ReceiveFilesFactory(ServerFactory):
    def buildProtocol(self, addr):
        global _TrustedIPs
        try:
            if addr.host not in _TrustedIPs:
                prnt(2, 'connection from not trusted ip: %s' % addr.host)
                return None
        except:
            return None
        p = ReceiveFiles()
        p.factory = self
        return p

def receive(port):
    prnt(2, "receive going to listen on port "+ str(port))

    def _try_receiving(port, count):
        prnt(2, "receive count=%d" % count)
        f = ReceiveFilesFactory()
        try:
            mylistener = reactor.listenTCP(int(port), f)
        except:
            mylistener = None
        return mylistener

    def _loop(port, result, count):
        l = _try_receiving(port, count)
        if l is not None:
            prnt(4, "receive started on port "+ str(port))
            result.callback(l)
            return
        if count > 10:
            prnt(1, "receive WARNING port %s is busy!" % str(port))
            result.errback(None)
            return
        reactor.callLater(10, _loop, port, result, count+1)

    res = Deferred()
    _loop(port, res, 0)
    return res


#-------------------------------------------------------------------------------

def usage():
        print '''Usage:
server.py [destination folder] [port]
'''

def main():
    if len(sys.argv) == 3:
        init()
        r = receive(sys.argv[2])
        reactor.run()
    else:
        usage()


if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding(locale.getpreferredencoding())
    main()

