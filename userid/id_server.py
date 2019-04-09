#!/usr/bin/env python
# id_server.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (id_server.py) is part of BitDust Software.
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


"""
.. module:: id_server.

.. role:: red
BitDust id_server() Automat

EVENTS:
    * :red:`incoming-identity-file`
    * :red:`init`
    * :red:`server-down`
    * :red:`shutdown`
    * :red:`start`
    * :red:`stop`
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from io import BytesIO

#------------------------------------------------------------------------------

import os
import sys
import struct

from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet.protocol import ServerFactory
from twisted.internet.defer import Deferred, DeferredList
from twisted.protocols import basic
from twisted.web import server, resource, static

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))

#------------------------------------------------------------------------------

from logs import lg

from system import bpio
from system import tmpfile

from automats import automat

from lib import strng
from lib import nameurl
from lib import misc
from lib import net_misc

from main import settings

from userid import identity
from userid import known_servers

#------------------------------------------------------------------------------

_IdServer = None

#------------------------------------------------------------------------------


def A(event=None, *args, **kwargs):
    """
    Access method to interact with the state machine.
    """
    global _IdServer
    if _IdServer is None:
        # set automat name and starting state here
        _IdServer = IdServer(
            name='id_server',
            state='AT_STARTUP',
            debug_level=2,
            log_events=True,
            log_transitions=True,
        )
    if event is None:
        return _IdServer
    _IdServer.automat(event, *args, **kwargs)


class IdServer(automat.Automat):
    """
    This class implements all the functionality of the ``id_server()`` state
    machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the
        state machine.
        """
        self.web_listener = None
        self.tcp_listener = None
        self.web_port = settings.IdentityWebPort()
        self.tcp_port = settings.IdentityServerPort()
        self.hostname = ''

    def A(self, event, *args, **kwargs):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'STOPPED'
                self.doInit(*args, **kwargs)
        #---LISTEN---
        elif self.state == 'LISTEN':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doSetDown(*args, **kwargs)
                self.doDestroyMe(*args, **kwargs)
            elif event == 'incoming-identity-file':
                self.doCheckAndSaveIdentity(*args, **kwargs)
            elif event == 'stop':
                self.state = 'DOWN'
                self.Restart = False
                self.doSetDown(*args, **kwargs)
        #---STOPPED---
        elif self.state == 'STOPPED':
            if event == 'start':
                self.state = 'LISTEN'
                self.doSetUp(*args, **kwargs)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        #---CLOSED---
        elif self.state == 'CLOSED':
            pass
        #---DOWN---
        elif self.state == 'DOWN':
            if event == 'server-down' and self.Restart:
                self.state = 'LISTEN'
                self.doSetUp(*args, **kwargs)
            elif event == 'start':
                self.Restart = True
            elif event == 'server-down' and not self.Restart:
                self.state = 'STOPPED'
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(*args, **kwargs)
        return None

    def doInit(self, *args, **kwargs):
        """
        Action method.
        """
        self.web_port, self.tcp_port = args[0]

    def doSetUp(self, *args, **kwargs):
        """
        Action method.
        """
        self.hostname = settings.getIdServerHost()
        if self.hostname == '':
            self.hostname = strng.to_bin(misc.readExternalIP())  # bpio.ReadTextFile(settings.ExternalIPFilename())
        if self.hostname == '':
            self.hostname = net_misc.getLocalIp()
        lg.out(4, 'id_server.doSetUp hostname=%s' % strng.to_text(self.hostname))
        if not os.path.isdir(settings.IdentityServerDir()):
            os.makedirs(settings.IdentityServerDir())
            lg.out(4, '            created a folder %s' % settings.IdentityServerDir())
        root = WebRoot()
        root.putChild(b'', WebMainPage())
        try:
            self.tcp_listener = reactor.listenTCP(self.tcp_port, IdServerFactory())  # @UndefinedVariable
            lg.out(4, "            identity server listen on TCP port %d started" % (self.tcp_port))
        except:
            lg.out(4, "id_server.set_up ERROR exception trying to listen on port " + str(self.tcp_port))
            lg.exc()
        try:
            self.web_listener = reactor.listenTCP(self.web_port, server.Site(root))  # @UndefinedVariable
            lg.out(4, "            have started web server at port %d   hostname=%s" % (
                self.web_port, strng.to_text(self.hostname), ))
        except:
            lg.out(4, "id_server.set_up ERROR exception trying to listen on port " + str(self.web_port))
            lg.exc()

    def doSetDown(self, *args, **kwargs):
        """
        Action method.
        """
        lg.out(4, "id_server.doSetDown")
        shutlist = []
        if self.web_listener:
            d = self.web_listener.stopListening()
            if d:
                shutlist.append(d)
            lg.out(4, "            stopped web listener")
        if self.tcp_listener:
            d = self.tcp_listener.stopListening()
            if d:
                shutlist.append(d)
            lg.out(4, "            stopped TCP listener")
        self.web_listener = None
        self.tcp_listener = None
        DeferredList(shutlist).addBoth(lambda x: self.automat('server-down'))

    def doCheckAndSaveIdentity(self, *args, **kwargs):
        """
        Action method.
        """
        self._save_identity(args[0])

    def doDestroyMe(self, *args, **kwargs):
        """
        Action method.
        """
        self.destroy()
        global _IdServer
        _IdServer = None
        if args and args[0] and len(args[0]) > 0 and isinstance(args[0][-1], Deferred):
            args[0][-1].callback(True)

    def _save_identity(self, inputfilename):
        """
        """
        lg.out(6, "id_server._save_identity " + inputfilename)
        if os.path.getsize(inputfilename) > 50000:
            lg.warn("input file too big - ignoring ")
            tmpfile.erase('idsrv', inputfilename, 'input file too big')
            # os.remove(inputfilename)
            return
        newxml = bpio.ReadTextFile(inputfilename)
        if len(newxml.strip()) < 500:
            lg.warn("input file too small - ignoring ")
            tmpfile.erase('idsrv', inputfilename, 'input file too small')
            # os.remove(inputfilename)
            return
        try:
            newidentity = identity.identity(xmlsrc=newxml)
        except:
            lg.warn("input file is wrong - ignoring ")
            tmpfile.erase('idsrv', inputfilename, 'input file is wrong')
            # os.remove(inputfilename)
            return
        tmpfile.erase('idsrv', inputfilename, 'id received')
        if not newidentity.isCorrect():
            lg.warn("has non-Correct identity")
            return
        if not newidentity.Valid():
            lg.warn("has non-Valid identity")
            return
        matchid = ""
        for idurl in newidentity.sources:
            protocol, host, port, filename = nameurl.UrlParse(idurl)
            if strng.to_text(host) == strng.to_text(self.hostname):
                lg.out(4, "id_server._save_identity found match for us")
                matchid = idurl
                break
        if matchid == "":
            lg.warn("identity is not for this nameserver")
            return
        protocol, host, port, filename = nameurl.UrlParse(matchid)
        name, justxml = filename.split(".")
        # SECURITY check that name is simple
        if justxml != "xml":
            lg.warn("identity name " + filename)
            return
        if len(name) > settings.MaximumUsernameLength():
            lg.warn("identity name " + filename)
            return
        if len(name) < settings.MinimumUsernameLength():
            lg.warn("identity name " + filename)
            return
        for c in name:
            if c not in settings.LegalUsernameChars():
                lg.warn("identity name " + filename)
                return
        localfilename = os.path.join(settings.IdentityServerDir(), filename)
    #    lg.out(8,"id_server.SaveIdentity with filename " + localfilename)
        oldxml = ''
        # need to make sure id was not already used by different key - which would mean someone trying to steal identity
        if os.path.exists(localfilename):
            lg.out(6, "id_server._save_identity was already an identity with this name " + localfilename)
            oldxml = bpio.ReadTextFile(localfilename)
            oldidentity = identity.identity(xmlsrc=oldxml)
            if oldidentity.publickey != newidentity.publickey:
                lg.warn("new public key does not match old " + localfilename)
                return
        if newxml != oldxml:
            if not os.path.exists(localfilename):
                lg.out(6, "id_server._save_identity will save NEW Identity: " + filename)
            bpio.WriteTextFile(localfilename, newxml)

#------------------------------------------------------------------------------


class IdServerProtocol(basic.Int32StringReceiver):

    def __init__(self):
        self.fpath = None     # string with path/filename
        self.fin = None         # integer file descriptor like os.open() returns
        self.received = 0

    def disconnect(self):
        try:
            self.transport.stopListening()
        except:
            try:
                self.transport.loseConnection()
            except:
                lg.exc()

    def connectionMade(self):
        """
        """
        # lg.out(8, 'id_server.connectionMade from ' + str(self.transport.getPeer()))

    def stringReceived(self, data):
        try:
            version = strng.to_bin(data[0:1])
            command = strng.to_bin(data[1:2])
            payload = data[2:]
        except:
            self.disconnect()
            # self.transport.loseConnection()
            lg.exc()
            lg.warn('incorrect data from %s\n' % str(self.transport.getPeer()))
            return
        if command == b'h':
            # lg.out(6, 'id_server.stringReceived HELLO received from %s' % payload)
            # self.sendString(strng.to_bin(
            #     '%swid-server:%s' % (version, strng.to_text(A().hostname))))
            self.sendString(version + b'wid-server:' + strng.to_bin(A().hostname))
            return
        if command != b'd':
            self.disconnect()
            # self.transport.loseConnection()
            lg.warn('not a "data" packet from %s : %r' % (str(self.transport.getPeer()), data))
            return
        inp = BytesIO(payload)
        try:
            file_id = int(struct.unpack('i', inp.read(4))[0])
            file_size = int(struct.unpack('i', inp.read(4))[0])
        except:
            inp.close()
            self.disconnect()
            # self.transport.loseConnection()
            lg.exc()
            lg.warn('wrong data from %s' % str(self.transport.getPeer()))
            return
        if self.fin is None:
            self.fin, self.fpath = tmpfile.make('idsrv', extension='.xml')
        inp_data = inp.read()
        inp.close()
        os.write(self.fin, inp_data)
        self.received += len(inp_data)
        # self.transport.loseConnection()
        self.sendString(version + b'o' + struct.pack('i', file_id))
        # self.sendString(strng.to_bin('%so%s' % (version, struct.pack('i', file_id))))
        # lg.out(6, 'id_server.stringReceived  %d bytes received from %s' % (len(data), str(self.transport.getPeer())))
        if self.received == file_size:
            os.close(self.fin)
            A('incoming-identity-file', self.fpath)
            self.fin = None
            self.fpath = None
            # self.disconnect()

    def connectionLost(self, reason):
        """
        """

#------------------------------------------------------------------------------


class IdServerFactory(ServerFactory):

    def buildProtocol(self, addr):
        p = IdServerProtocol()
        p.factory = self
        return p

#------------------------------------------------------------------------------


class WebMainPage(resource.Resource):

    def render(self, request):
        src = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<title>Identities on %(hostname)s</title>
<style>
body{margin: 0 auto; padding: 0;}
#content {margin: 0 auto; padding: 0; text-align: justify; line-height: 1.7;
min-height: 500px; width: 960px; font-size: 18px; text-decoration: none;
font-family: "Tw Cen MT", "Century Gothic", Futura, Arial, sans-serif;}
</style>
</head>
<body>
<div id="content">
<h1 align=center>Identities on %(hostname)s</h1>
''' % {'hostname': strng.to_text(A().hostname)}
        src += '<table cellspacing=0 width=100% border=0><tr valign=top>\n'
        src += '<td width=152px nowrap>\n'
        HTDOCS_DIR = settings.IdentityServerDir()
        files = []
        if os.path.isdir(HTDOCS_DIR):
            for filename in os.listdir(HTDOCS_DIR):
                filepath = os.path.join(HTDOCS_DIR, filename)
                if os.path.isdir(filepath):
                    continue
                if not filename.endswith('.xml'):
                    continue
                files.append(filename)
        files.sort()
        currentChar = ''
        charIndex = 0
        for filename in files:
            if filename[0] != currentChar:
                currentChar = filename[0]
                if charIndex % 4 == 3:
                    src += '\n</td>\n<td width=152px nowrap>\n'
                charIndex += 1
                src += '\n<br>\n<h3>%s</h3>\n' % str(currentChar).upper()
            url = '/' + filename
            name = filename[:-4]
            src += '<p><a href="%s"><nobr>%s</nobr></a></p>\n' % (strng.to_text(url), strng.to_text(name))
        src += '</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr><td align=left>'
        src += '<br><br><p>Total identities on "%s": %d</p><br><br>\n' % (strng.to_text(A().hostname), len(files))
        src += '<p>Other known identity servers:\n'
        for idhost in sorted(known_servers.by_host().keys()):
            idport = known_servers.by_host()[idhost][0]
            if idport != 80:
                idhost += b':%d' % idport
            src += '<a href="http://%s/"><nobr>%s</nobr></a>&nbsp;&nbsp;\n' % (strng.to_text(idhost), strng.to_text(idhost))
        src += '</p>'
        src += '<!--CLIENT_HOST=%s:%s-->\n' % (request.client.host, request.client.port)
        src += '</body>\n</html>'
        del files
        return strng.to_bin(src)

#------------------------------------------------------------------------------


class WebRoot(resource.Resource):

    def getChild(self, path, request):
        if not path:
            return self
        filepath = os.path.join(settings.IdentityServerDir(), strng.to_text(path))
        if os.path.isfile(filepath):
            return static.File(filepath)
        return resource.NoResource('Not found')

#------------------------------------------------------------------------------


def main():
    bpio.init()
    settings.init()
    if len(sys.argv) > 1:
        web_port = int(sys.argv[1])
    else:
        web_port = settings.getIdServerWebPort()
    if len(sys.argv) > 2:
        tcp_port = int(sys.argv[2])
    else:
        tcp_port = settings.getIdServerTCPPort()
    lg.set_debug_level(20)
    lg.out(2, 'starting ID server ...')
    reactor.addSystemEventTrigger('before', 'shutdown',  # @UndefinedVariable
                                  A().automat, 'shutdown')
    reactor.callWhenRunning(A, 'init', (web_port, tcp_port))  # @UndefinedVariable
    reactor.callLater(0, A, 'start')  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    lg.out(2, 'reactor stopped, EXIT')

#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
