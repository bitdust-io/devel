

"""
.. module:: id_registrator
.. role:: red


EVENTS:
    * :red:`id-exist`
    * :red:`id-not-exist`
    * :red:`id-server-failed`
    * :red:`id-server-response`
    * :red:`local-ip-detected`
    * :red:`my-id-exist`
    * :red:`my-id-failed`
    * :red:`my-id-sent`
    * :red:`start`
    * :red:`stun-failed`
    * :red:`stun-success`
    * :red:`timer-10sec`
    * :red:`timer-30sec`
    * :red:`timer-5sec`
"""

import os
import sys
import random
import time

from twisted.internet.defer import Deferred, DeferredList

try:
    from logs import lg
except:
    dirpath = os.path.dirname(os.path.abspath(sys.argv[0]))
    sys.path.insert(0, os.path.abspath(os.path.join(dirpath, '..')))

from logs import lg

from lib import automat
from lib import bpio
from lib import misc
from lib import settings
from lib import stun
from lib import nameurl
from lib import net_misc
from lib import tmpfile

from crypto import key

from transport import gate
from transport import callback

import identity
import known_servers

#------------------------------------------------------------------------------ 

_IdRegistrator = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _IdRegistrator
    if _IdRegistrator is None:
        # set automat name and starting state here
        _IdRegistrator = IdRegistrator('id_registrator', 'AT_STARTUP')
    if event is not None:
        _IdRegistrator.automat(event, arg)
    return _IdRegistrator


class IdRegistrator(automat.Automat):
    """
    This class implements all the functionality of the ``id_registrator()`` state machine.
    """

    timers = {
        'timer-30sec': (30.0, ['NAME_FREE?']),
        'timer-10sec': (10.0, ['SEND_ID','REQUEST_ID']),
        'timer-5sec': (5.0, ['REQUEST_ID']),
        }

    MESSAGES = {
        'MSG_0': ['ping ID servers'],
        'MSG_1': ['checking the availability of a user name'],
        'MSG_2': ['checking network configuration'],
        'MSG_3': ['detecting external IP'],
        'MSG_4': ['registering on ID servers'],
        'MSG_5': ['verifying my identity'],
        'MSG_6': ['new user %(login)s registered successfully!', 'green'], 
        'MSG_7': ['ID servers not responding', 'red'],
        'MSG_8': ['name %(login)s already taken', 'red'],
        'MSG_9': ['network connection error', 'red'],
        'MSG_10':['connection error while sending my identity', 'red'],
        'MSG_11':['identity verification failed', 'red'],
        'MSG_12':['time out requesting from identity server', 'red'],
        'MSG_13':['time out sending to identity server', 'red'],
        }

    def msg(self, msgid, arg=None): 
        msg = self.MESSAGES.get(msgid, ['', 'black'])
        text = msg[0] % {
            'login': bpio.ReadTextFile(settings.UserNameFilename()),
            'externalip': bpio.ReadTextFile(settings.ExternalIPFilename()),
            'localip': bpio.ReadTextFile(settings.LocalIPFilename()),}
        color = 'black'
        if len(msg) == 2:
            color = msg[1]
        return text, color

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.discovered_servers = []
        self.good_servers = []
        self.registrations = []
        self.free_idurls = []
        self.new_identity = None

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """
        from p2p import installer
        installer.A('id_registrator.state', newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'ID_SERVERS?'
                self.doSaveMyName(arg)
                self.doSelectRandomServers(arg)
                self.doPingServers(arg)
                self.doPrint(self.msg('MSG_0', arg))
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---ID_SERVERS?---
        elif self.state == 'ID_SERVERS?':
            if ( event == 'id-server-response' or event == 'id-server-failed' ) and self.isAllTested(arg) and self.isSomeAlive(arg) :
                self.state = 'NAME_FREE?'
                self.doRequestServers(arg)
                self.doPrint(self.msg('MSG_1', arg))
            elif ( event == 'id-server-response' or event == 'id-server-failed' ) and self.isAllTested(arg) and not self.isSomeAlive(arg) :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_7', arg))
                self.doDestroyMe(arg)
        #---NAME_FREE?---
        elif self.state == 'NAME_FREE?':
            if event == 'id-not-exist' and self.isAllResponded(arg) and self.isFreeIDURLs(arg) :
                self.state = 'LOCAL_IP'
                self.doDetectLocalIP(arg)
                self.doPrint(self.msg('MSG_2', arg))
            elif event == 'timer-30sec' or ( event == 'id-exist' and self.isAllResponded(arg) and not self.isFreeIDURLs(arg) ) :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_8', arg))
                self.doDestroyMe(arg)
        #---LOCAL_IP---
        elif self.state == 'LOCAL_IP':
            if event == 'local-ip-detected' :
                self.state = 'EXTERNAL_IP'
                self.doStunExternalIP(arg)
                self.doPrint(self.msg('MSG_3', arg))
        #---EXTERNAL_IP---
        elif self.state == 'EXTERNAL_IP':
            if event == 'stun-success' :
                self.state = 'SEND_ID'
                self.doCreateMyIdentity(arg)
                self.doSendMyIdentity(arg)
                self.doPrint(self.msg('MSG_4', arg))
            elif event == 'stun-failed' :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_9', arg))
                self.doDestroyMe(arg)
        #---SEND_ID---
        elif self.state == 'SEND_ID':
            if event == 'my-id-sent' :
                self.state = 'REQUEST_ID'
                self.doRequestMyIdentity(arg)
                self.doPrint(self.msg('MSG_5', arg))
            elif event == 'my-id-failed' :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_10', arg))
                self.doDestroyMe(arg)
            elif event == 'timer-10sec' :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_13', arg))
                self.doDestroyMe(arg)
        #---REQUEST_ID---
        elif self.state == 'REQUEST_ID':
            if event == 'my-id-exist' and self.isMyIdentityValid(arg) :
                self.state = 'DONE'
                self.doSaveMyIdentity(arg)
                self.doDestroyMe(arg)
                self.doPrint(self.msg('MSG_6', arg))
            elif event == 'timer-5sec' :
                self.doRequestMyIdentity(arg)
            elif event == 'my-id-exist' and not self.isMyIdentityValid(arg) :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_11', arg))
                self.doDestroyMe(arg)
            elif event == 'timer-10sec' :
                self.state = 'FAILED'
                self.doPrint(self.msg('MSG_12', arg))
                self.doDestroyMe(arg)

    def isMyIdentityValid(self, arg):
        """
        Condition method.
        """
        id_from_server = identity.identity(xmlsrc=arg)
        if not id_from_server.Valid():
            return False
        return self.new_identity.serialize() == id_from_server.serialize()
    
    def isSomeAlive(self, arg):
        """
        Condition method.
        """
        return len(self.good_servers) > 0
        

    def isAllResponded(self, arg):
        """
        Condition method.
        """
        return len(self.registrations) == 0
        
    def isAllTested(self, arg):
        """
        Condition method.
        """
        return len(self.discovered_servers) == 0

    def isFreeIDURLs(self, arg):
        """
        Condition method.
        """
        return len(self.free_idurls) > 0

    def doSelectRandomServers(self, arg):
        """
        Action method.
        """
        # In future we can do search such peers in DHT.
        for i in range(3):
            s = set(known_servers.by_host().keys())
            s.difference_update(self.discovered_servers)
            if len(s) > 0:
                self.discovered_servers.append(random.choice(list(s)))
        lg.out(4, 'id_registrator.doSelectRandomServers %s' % str(self.discovered_servers))        

    def doPingServers(self, arg):
        """
        Action method.
        """
        lg.out(4, 'id_registrator.doPingServers    %d in list' % len(self.discovered_servers))
        def _cb(htmlsrc, id_server_host):
            lg.out(4, '            RESPONDED: %s' % id_server_host)
            self.good_servers.append(id_server_host)
            self.discovered_servers.remove(id_server_host)
            self.automat('id-server-response', (id_server_host, htmlsrc))
        def _eb(err, id_server_host):
            lg.out(4, '               FAILED: %s' % id_server_host)
            self.discovered_servers.remove(id_server_host)
            self.automat('id-server-failed', (id_server_host, err))            
        for host in self.discovered_servers:
            webport, tcpport = known_servers.by_host().get(host, 
                (settings.IdentityWebPort(), settings.IdentityServerPort()))
            if webport == 80:
                webport = ''
            server_url = nameurl.UrlMake('http', host, webport, '')
            d = net_misc.getPageTwisted(server_url, timeout=10)
            d.addCallback(_cb, host)
            d.addErrback(_eb, host)

    def doRequestServers(self, arg):
        """
        Action method.
        """
        login = bpio.ReadTextFile(settings.UserNameFilename())
        def _cb(xmlsrc, idurl, host):
            lg.out(4, '                EXIST: %s' % idurl)
            self.registrations.remove(idurl)
            self.automat('id-exist', idurl)
        def _eb(err, idurl, host):
            lg.out(4, '            NOT EXIST: %s' % idurl)
            self.free_idurls.append(idurl)
            self.registrations.remove(idurl)
            self.automat('id-not-exist', idurl)        
        for host in self.good_servers:
            webport, tcpport = known_servers.by_host().get(
                host, (settings.IdentityWebPort(), settings.IdentityServerPort()))
            if webport == 80:
                webport = ''
            idurl = nameurl.UrlMake('http', host, webport, login+'.xml')
            lg.out(4, '    %s' % idurl)
            d = net_misc.getPageTwisted(idurl, timeout=10)
            d.addCallback(_cb, idurl, host)
            d.addErrback(_eb, idurl, host)
            self.registrations.append(idurl)
        lg.out(4, 'id_registrator.doRequestServers login=%s registrations=%d' % (login, len(self.registrations)))

    def doDetectLocalIP(self, arg):
        """
        Action method.
        """
        localip = net_misc.getLocalIp()
        bpio.WriteFile(settings.LocalIPFilename(), localip)
        lg.out(4, 'id_registrator.doDetectLocalIP [%s]' % localip)
        self.automat('local-ip-detected')        

    def doStunExternalIP(self, arg):
        """
        Action method.
        """
        lg.out(4, 'id_registrator.doStunExternalIP')
        def save(ip):
            lg.out(4, '            external IP is %s' % ip)
            bpio.WriteFile(settings.ExternalIPFilename(), ip)
            self.automat('stun-success', ip)
        stun.stunExternalIP(
            close_listener=True,  # False, 
            internal_port=settings.getUDPPort(),).addCallbacks(
                save, lambda x: self.automat('stun-failed'))

    def doSaveMyName(self, arg):
        """
        Action method.
        """
        login = arg
        lg.out(4, 'id_registrator.doSaveMyName [%s]' % login)
        bpio.WriteFile(settings.UserNameFilename(), login)

    def doCreateMyIdentity(self, arg):
        """
        Action method.
        """
        self.create_new_identity()

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        mycurrentidentity = misc.getLocalIdentity()
        misc.setLocalIdentity(self.new_identity)
        def _cb(x):
            misc.setLocalIdentity(mycurrentidentity)
            self.automat('my-id-sent')
        def _eb(x):
            misc.setLocalIdentity(mycurrentidentity)
            self.automat('my-id-failed')
        dl = self.send_new_identity()
        dl.addCallback(_cb)
        dl.addErrback(_eb)

    def doRequestMyIdentity(self, arg):
        """
        Action method.
        """
        lg.out(8, 'id_registrator.doRequestMyIdentity')
        def _cb(src):
            self.automat('my-id-exist', src)
        def _eb(err):
            self.automat('my-id-not-exist', err)
        for idurl in self.new_identity.sources:
            lg.out(8, '        %s' % idurl)
            d = net_misc.getPageTwisted(idurl, timeout=20)
            d.addCallback(_cb)
            d.addErrback(_eb)

    def doSaveMyIdentity(self, arg):
        """
        Action method.
        """
        misc.setLocalIdentity(self.new_identity)
        misc.saveLocalIdentity()
        
    def doDestroyMe(self, arg):
        """
        Action method.
        """
        automat.objects().pop(self.index)
        global _IdRegistrator
        _IdRegistrator = None
    
    def doPrint(self, arg):
        """
        Action method.
        """
        from p2p import installer
        installer.A().event('print', arg)

    def create_new_identity(self):
        """
        Generate new Private key and new identity file.
        Reads some extra info from config files.
        """
        key.InitMyKey()
#        misc.loadLocalIdentity()
#        if misc.isLocalIdentityReady():
#            try:
#                lid = misc.getLocalIdentity()
#                lid.sign()
#                valid = lid.Valid()
#            except:
#                valid = False
#                lg.exc()
#            if valid:
#                self.new_identity = lid
#                lg.out(2, 'id_registrator.create_new_identity   found existing local identity!!!!!!!!!!')
#                return
#            lg.out(2, 'id_registrator.create_new_identity WARNING existing local identity is not VALID')
    
        login = bpio.ReadTextFile(settings.UserNameFilename())
        externalIP = bpio.ReadTextFile(settings.ExternalIPFilename())
        localIP = bpio.ReadTextFile(settings.LocalIPFilename())
        lg.out(4, 'id_registrator.create_new_identity %s %s ' % (login, externalIP))
        ident = identity.identity()
        ident.default()
        ident.sources = []
        ident.sources.extend(self.free_idurls)
        cdict = {}
        if settings.enableTCP():
            cdict['tcp'] = 'tcp://'+externalIP+':'+settings.getTCPPort()
        if settings.enableDHTUDP():
            try:
                protocol, host, port, filename = nameurl.UrlParse(ident.sources[0])
                if port and port != '80':
                    host += '_%d' % int(port) 
                cdict['dhtudp'] = 'dhtudp://%s@%s' % (login.lower(), host)
            except:
                lg.exc()
        for c in misc.validTransports:
            if cdict.has_key(c):
                ident.contacts.append(cdict[c])
        ident.publickey = key.MyPublicKey()
        ident.date = time.ctime() #time.strftime('%b %d, %Y')
        revnum = bpio.ReadTextFile(settings.RevisionNumberFile()).strip()
        repo, location = misc.ReadRepoLocation()
        ident.version = (revnum.strip() + ' ' + repo.strip() + ' ' + bpio.osinfo().strip()).strip()
        ident.sign()
        bpio.WriteFile(settings.LocalIdentityFilename()+'.new', ident.serialize())
        self.new_identity = ident
        
    def send_new_identity(self):
        """
        Send created identity to the identity server to register it. 
        """
        lg.out(4, 'id_registrator.send_new_identity ')
        gate.init()
        gate.start()
        sendfilename = settings.LocalIdentityFilename()+'.new'
        dlist = []
        for idurl in self.new_identity.sources:
            self.free_idurls.remove(idurl)
            protocol, host, port, filename = nameurl.UrlParse(idurl)
            webport, tcpport = known_servers.by_host().get(
                host, (settings.IdentityWebPort(), settings.IdentityServerPort()))
            srvhost = '%s:%d' % (host, tcpport)
            dlist.append(gate.send_file_single(
                'tcp', srvhost, sendfilename, 'Identity'))
        assert len(self.free_idurls) == 0
        return DeferredList(dlist)

#------------------------------------------------------------------------------ 

def main():
    bpio.init()
    settings.init()
    lg.set_debug_level(20)
    from twisted.internet import reactor
    reactor.callWhenRunning(A, 'start', sys.argv[1])
    reactor.run()

if __name__ == "__main__":
    main()

