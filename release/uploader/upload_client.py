#!/usr/bin/python
#client.py

import os
import sys
import codecs
import locale
import hashlib


try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in upload_client.py')


from twisted.internet import task
from twisted.internet import protocol
from twisted.internet.protocol import ServerFactory, ClientFactory
from twisted.protocols import basic
from twisted.internet.defer import Deferred
from twisted.python import log

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
    sys.stdout.write(unicode(' ' * offs + str + new_line).encode(sys.stdout.encoding))
    
def get_hash(src):
    return hashlib.md5(src).hexdigest()

def file_hash(path):
    src = read_binary_file(path)
    if not src:
        return None
    return get_hash(src)    

#-------------------------------------------------------------------------------

class Putter(protocol.Protocol):
    fin = None
    files = []
    answers = {}
    current = 0
    current_length = 0
    current_length_gzipped = 0
    count_different = 0
    count_new = 0
    basepath = ''
    buf = ''
    def connectionMade(self):
        prnt(4, 'connection made with host ' + self.factory.host)
        self.basepath = os.path.abspath(self.factory.path)
        if os.path.isdir(self.basepath):
            self.files = list_dir_recursive(self.basepath)
        elif os.path.isfile(self.basepath):
            self.files.append(self.basepath)
            self.basepath = os.path.dirname(self.basepath)
        #print '\n'.join(self.files)
        if len(self.files) == 0:
            self.transport.loseConnection()
            if self.factory.d is not None:
                self.factory.d.callback('empty folder')
            return
        # move info.txt to the bottom of the list
        for i in range(len(self.files)):
            filepath = self.files[i]
            if filepath.count('info.txt'):
                self.files.pop(i)
                self.files.append(filepath)
                prnt(6, 'info.txt moved to the end of list')
                break
        # move version.txt to the bottom of the list
        for i in range(len(self.files)):
            filepath = self.files[i]
            if filepath.count('version.txt'):
                self.files.pop(i)
                self.files.append(filepath)
                prnt(6, 'version.txt moved to the end of list')
                break
        # start
        self.sendHashes()
        #self.startNext()

    def sendHashes(self):
        prnt(4, 'sending hash values, %d files' % len(self.files))
        for filepath in self.files:
            filename = filepath[len(self.basepath)+1:]
            filename = filename.replace('\\', '/')
            self.transport.write(filename+'\n')
            self.transport.write(file_hash(filepath)+'\n')
            self.transport.write('?\n')
            self.transport.write('?\n')
            prnt(6, filename)

    def startNext(self):
        if self.current >= len(self.files):
            self.transport.loseConnection()
            if self.factory.d is not None:
                self.factory.d.callback('finished')
            return

        filepath = self.files[self.current]
        filename = filepath[len(self.basepath)+1:]
        filename = filename.replace('\\', '/')

        if self.answers[filename] == 'equal':
            self.current += 1
            reactor.callLater(0, self.startNext)
            return

        try:
            self.fin = file(filepath, 'rb')
            self.fin.seek(0, 2)
            length = self.fin.tell()
            self.current_length = length
            self.fin.seek(0)
            self.fin.close()
            if os.path.isfile(filepath+'.gz'):               
                os.remove(filepath+'.gz')
            os.system('gzip -9 -c "' + filepath + '" >"' + filepath + '.gz"')
            self.fin = file(filepath + '.gz', 'rb')
            self.fin.seek(0, 2)
            length_gzipped = self.fin.tell()
            self.current_length_gzipped = length_gzipped
            self.fin.seek(0)
        except:
            self.transport.loseConnection()
            if self.factory.d is not None:
                self.factory.d.errback('failed to read ' + filepath)
            return

        self.transport.write(filename+'\n')
        self.transport.write(file_hash(filepath)+'\n')
        self.transport.write(str(length)+'\n')
        self.transport.write(str(length_gzipped)+'\n')

    def stateReceived(self, remote_filename, state):
        filepath = self.files[self.current]
        filename = filepath[len(self.basepath)+1:]
        filename = filename.replace('\\', '/')

        if state == 'done':
            if filename == remote_filename:
                os.remove(filepath+'.gz')
                self.current += 1
                prnt(0, '', '\n')
                reactor.callLater(0, self.startNext)

        elif state == 'ready':
            if filename == remote_filename:
                self.sendFile()
                prnt(4, '[%s] %s %s ' % (
                        ('%d/%d' % (self.current, len(self.files))).ljust(9),
                        ('(%dKb/%dKb)' % (round(float(self.current_length)/1024.0, 2), 
                                          round(float(self.current_length_gzipped)/1024.0, 2))).ljust(20), 
                        os.path.basename(filename).ljust(40)), new_line='')

        elif state in ['equal', 'different', 'noexist']:
            self.answers[remote_filename] = state
            if state == 'different':
                self.count_different += 1
                prnt(6, '[diff] %s' % remote_filename)
            if state == 'noexist':
                self.count_new += 1
                prnt(6, '[ new] %s' % remote_filename)
            if len(self.answers) == len(self.files):
                prnt(4, 'total files:      %d' % len(self.files))
                prnt(4, 'different files:  %d' % self.count_different)
                prnt(4, 'new files:        %d' % self.count_new)
                prnt(4, 'files to be send: %d' % (self.count_new + self.count_different))
                self.startNext()

        else:
            if filename == remote_filename:
                prnt(0, '.', new_line='')
                

    def dataReceived(self, data):
        self.buf += data
        while True:
            try:
                remote_filename, state, self.buf = self.buf.split('\n', 2)
                reactor.callLater(0, self.stateReceived, remote_filename, state)
            except:
                break

    def sendFile(self):
        fs = basic.FileSender()
        d = fs.beginFileTransfer(self.fin, self.transport)
        d.addCallback(self.finishedTransfer)
        d.addErrback(self.transferFailed)

    def finishedTransfer(self, result):
        try:
            self.fin.close()
        except:
            prnt(1, 'Putter.finishedTransfer ERROR close file failed')

    def transferFailed(self, err):
        prnt(1, 'Putter.transferFailed NETERROR current=' + str(self.current))
        try:
            self.fin.close()
        except:
            pass
        self.current += 1
        self.startNext()
##        self.transport.loseConnection()
##        if self.factory.d is not None:
##            self.factory.d.errback('failed')

    def connectionLost(self, reason):
        #prnt(14, 'Putter.connectionLost host=' + self.factory.host)
        #self.transport.loseConnection()
        try:
            self.fin.close()
        except:
            pass

class SendingFactory(ClientFactory):
    def __init__(self, path, host, port, d = None):
        self.path = path
        self.host = host
        self.port = port
        self.protocol = Putter
        self.d = d

    def clientConnectionFailed(self, connector, reason):
        ClientFactory.clientConnectionFailed(self, connector, reason)
        name = str(reason.type.__name__)
        prnt(10, 'clientConnectionFailed NETERROR [%s] with %s:%s' % (
            name,
            connector.getDestination().host,
            connector.getDestination().port,))


def send(path, host, port):
    d = Deferred()
    prnt(2, "send  %s  %s  %s " % (
        str(host), str(port), path))
    sender = SendingFactory(path, host, int(port), d)
    conn = reactor.connectTCP(host, int(port), sender)
    return d

#-------------------------------------------------------------------------------


def usage():
        print '''Usage:
client.py [folder/file] [host] [port]
'''

def main():
    def _done(x):
        try:
            msg = x.getErrorMessage()
        except:
            msg = str(x)
        print '[DONE]:', msg
        reactor.stop()
        os.system('pause')
    if len(sys.argv) == 4:
        if not os.path.exists(sys.argv[1]):
            print 'folder or file not exist'
            return
        r = send(sys.argv[1], sys.argv[2], sys.argv[3]).addBoth(_done)
        reactor.run()
    else:
        usage()


if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding(locale.getpreferredencoding())
    main()

