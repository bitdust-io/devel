#!/usr/bin/python
#processor.py
#
# <<<COPYRIGHT>>>
#
#
#
#

import os
import sys
import base64

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in processor.py')

from twisted.internet import stdio
from twisted.protocols import basic

import lib.io as io  

import make
import read 

#------------------------------------------------------------------------------ 

JobServer = None

#------------------------------------------------------------------------------ 
    
class Echo(basic.LineReceiver):
    delimiter = '\n'

    def connectionMade(self):
        self.sendLine('process-started')

    def lineReceived(self, line):
        try:
            words = line.split(' ')
            cmd = words[0]
            params = map(base64.b64decode, words[1:])
            io.log(4, '%s %s' % (cmd, params))
            if cmd == 'make':
                dataNum, parityNum = make.raidmake(params[0], params[1], params[2], int(params[3]), in_memory=True)
                self.sendLine('task-done %s %s' % (dataNum, parityNum))
            elif cmd == 'read':
                GoodDSegs = read.raidread(params[0], params[1], params[2], int(params[3]))
                self.sendLine('task-done %d' % GoodDSegs)
            # TODO:
            # elif cmd == 'rebuild': 
                # read.RebuildOne(inlist, listlen, outfilename)
        except:
            io.exception()
            self.sendLine('error')
            
#------------------------------------------------------------------------------ 

def main():
    if io.Windows():
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)

    io.init()
    logspath = os.path.join(os.path.expanduser('~'), '.bitpie', 'logs')
    if not os.path.isdir(logspath):
        logspath = 'raid.log'
    else:
        logspath = os.path.join(logspath, 'raid.log')
    io.OpenLogFile(logspath)
    io.SetDebug(20)

    io.HigherPriority()

    stdio.StandardIO(Echo())
        
    reactor.run()
    
    io.CloseLogFile()




