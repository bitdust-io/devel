#!/usr/bin/python
# net_misc.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (net_misc.py) is part of BitDust Software.
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
#
#
#
#
"""
.. module:: net_misc.

Some network routines
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
import six.moves.urllib.parse
import six
from io import open

#------------------------------------------------------------------------------

import os
import re
import sys
import socket
import random
import platform
import mimetypes
import subprocess
# fun mountain from
# python imports :-)

#------------------------------------------------------------------------------

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in net_misc.py')

from twisted.internet.defer import Deferred, DeferredList, succeed, fail
from twisted.internet import protocol
# from twisted.internet.utils import getProcessOutput
from twisted.web import iweb
from twisted.web import client
from twisted.web import http_headers
from twisted.web.client import downloadPage
from twisted.web.client import HTTPDownloader
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

from zope.interface import implementer

#------------------------------------------------------------------------------

_ConnectionDoneCallbackFunc = None
_ConnectionFailedCallbackFunc = None

#------------------------------------------------------------------------------

_UserAgentString = "BitDust-http-agent"
_ProxySettings = {
    'host': '',
    'port': '',
    'ssl': 'False',
    'username': '',
    'password': ''
}

#------------------------------------------------------------------------------


def init():
    """
    Just in case.
    """


def shutdown():
    """
    """

#------------------------------------------------------------------------------

def SetConnectionDoneCallbackFunc(f):
    """
    Here is a place to set a callback to catch events for ````successful````
    network transfers.
    """
    global _ConnectionDoneCallbackFunc
    _ConnectionDoneCallbackFunc = f


def SetConnectionFailedCallbackFunc(f):
    """
    Set a callback to catch events for ````failed```` network transfers or
    connections.

    Later, BitDust code will compare both counters to decide that
    connection to Internet is gone.
    """
    global _ConnectionFailedCallbackFunc
    _ConnectionFailedCallbackFunc = f


def ConnectionDone(param=None, proto=None, info=None):
    """
    This method is called from different places to inform of ````successful````
    network transfers, connections, requests.
    """
    global _ConnectionDoneCallbackFunc
    if _ConnectionDoneCallbackFunc is not None:
        _ConnectionDoneCallbackFunc(proto, info, param)
    return param


def ConnectionFailed(param=None, proto=None, info=None):
    """
    This method is called to inform of ````failed```` network results.
    """
    global _ConnectionFailedCallbackFunc
    if _ConnectionFailedCallbackFunc is not None:
        _ConnectionFailedCallbackFunc(proto, info, param)
    return param

#------------------------------------------------------------------------------

def normalize_address(host_port):
    """
    Input argument `host` can be string: "123.45.67.89:8080" or tuple: (b"123.45.67.89", 8080)
    Method always return tuple and make sure host is string/bytes but not unicode and port is integer.
    """
    if not host_port:
        return host_port
    if isinstance(host_port, six.binary_type):
        host_port = host_port.decode('utf-8')
    if isinstance(host_port, six.string_types):
        host_port = host_port.split(':')
        host_port = (host_port[0], int(host_port[1]), )
    if isinstance(host_port[0], six.text_type):
        host_port = (host_port[0].encode('utf-8'), int(host_port[1]), )
    return host_port


def pack_address(host_port):
    """
    Same as `normalize_address()`, but always return address as string/bytes: b"123.45.67.89:8080"
    """
    if not host_port:
        return host_port
    norm = normalize_address(host_port)
    return norm[0] + b':' + str(norm[1]).encode()

#------------------------------------------------------------------------------

def parse_url(url, defaultPort=None):
    """
    Split the given URL into the scheme, host, port, and path.
    """
    if isinstance(url, six.binary_type):
        url = url.decode('utf-8')
    url = url.strip()
    parsed = six.moves.urllib.parse.urlparse(url)
    scheme = parsed[0]
    path = six.moves.urllib.parse.urlunparse(('', '') + parsed[2:])
    if defaultPort is None:
        if scheme == 'https':
            defaultPort = 443
        else:
            defaultPort = 80
    host, port = parsed[1], defaultPort
    if ':' in host:
        host, port = host.rsplit(':', 1)
        try:
            port = int(port)
        except ValueError:
            port = defaultPort
    if not path:
        path = '/'
    return scheme, host, port, path


def parse_credentials(host):
    """
    Test host name (network location) for credentials and split by parts: host,
    username, password.
    """
    if not host.count('@'):
        return host, '', ''
    credentials, host = host.rsplit('@', 1)
    if not credentials.count(':'):
        return host, credentials, ''
    username, password = credentials.split(':', 1)
    return host, username, password

#------------------------------------------------------------------------------


def detect_proxy_settings():
    """
    Do some work and return dictionary with Proxy server settings for that
    machine.
    """
    d = {
        'host': '',
        'port': '',
        'username': '',
        'password': '',
        'ssl': 'False'}
    httpproxy = urllib2.getproxies().get('http', None)
    httpsproxy = urllib2.getproxies().get('https', None)

    if httpproxy is not None:
        try:
            scheme, host, port, path = parse_url(httpproxy)
            host, username, password = parse_credentials(host)
        except:
            return d
        d['ssl'] = 'False'
        d['host'] = host
        d['port'] = port
        d['username'] = username
        d['password'] = password

    if httpsproxy is not None:
        try:
            scheme, host, port, path = parse_url(httpsproxy)
            host, username, password = parse_credentials(host)
        except:
            return d
        d['ssl'] = 'True'
        d['host'] = host
        d['port'] = port
        d['username'] = username
        d['password'] = password

    return d


def set_proxy_settings(settings_dict):
    """
    Remember proxy settings.
    """
    global _ProxySettings
    _ProxySettings = settings_dict


def get_proxy_settings():
    """
    Get current proxy settings.
    """
    global _ProxySettings
    return _ProxySettings


def get_proxy_host():
    """
    Get current proxy host.
    """
    global _ProxySettings
    return _ProxySettings.get('host', '')


def get_proxy_port():
    """
    Get current proxy port number.
    """
    global _ProxySettings
    try:
        return int(_ProxySettings.get('port', '8080'))
    except:
        return 8080


def get_proxy_username():
    """
    Get current proxy username.
    """
    global _ProxySettings
    return _ProxySettings.get('username', '')


def get_proxy_password():
    """
    Get current proxy password.
    """
    global _ProxySettings
    return _ProxySettings.get('password', '')


def get_proxy_ssl():
    """
    Is this a secure proxy?
    """
    global _ProxySettings
    return _ProxySettings.get('ssl', '')


def proxy_is_on():
    """
    In most cases people do not use any proxy servers.

    This is to check if user is using a proxy and we have the settings.
    """
    return get_proxy_host() != ''

#------------------------------------------------------------------------------


def downloadPageTwisted(url, filename):
    """
    A wrapper for twisted method ``twisted.web.client.downloadPage``.
    """
    global _UserAgentString
    return downloadPage(url, filename, agent=_UserAgentString)

#-------------------------------------------------------------------------------


class HTTPProgressDownloader(HTTPDownloader):
    """
    Download to a file and keep track of progress.

    http://schwerkraft.elitedvb.net/plugins/scmcvs/cvsweb.php/enigma2-pl
    ugins/mediadownloader/src/HTTPProgressDownloader.py?rev=1.1;cvsroot=
    enigma2-plugins;only_with_tag=HEAD
    """

    def __init__(self, url, fileOrName, writeProgress=None, *args, **kwargs):
        HTTPDownloader.__init__(self, url, fileOrName, supportPartial=0, *args, **kwargs)
        # Save callback(s) locally
        if writeProgress and not isinstance(writeProgress, list):
            writeProgress = [writeProgress]
        self.writeProgress = writeProgress

        # Initialize
        self.currentlength = 0
        self.totallength = None

    def gotHeaders(self, headers):
        HTTPDownloader.gotHeaders(self, headers)

        # If we have a callback and 'OK' from Server try to get length
        if self.writeProgress and self.status == '200':
            if 'content-length' in headers:
                self.totallength = int(headers['content-length'][0])
                for cb in self.writeProgress:
                    if cb:
                        cb(0, self.totallength)

    def pagePart(self, data):
        HTTPDownloader.pagePart(self, data)

        # If we have a callback and 'OK' from server increment pos
        if self.writeProgress and self.status == '200':
            self.currentlength += len(data)
            for cb in self.writeProgress:
                if cb:
                    cb(self.currentlength, self.totallength)


def downloadWithProgressTwisted(url, file, progress_func):
    """
    This method can keep track of the progress.
    """
    global _UserAgentString
    from twisted.internet import ssl
    scheme, host, port, path = parse_url(url)
    factory = HTTPProgressDownloader(url, file, progress_func, agent=_UserAgentString)
    if scheme == 'https':
        contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory.deferred

#-------------------------------------------------------------------------------


def downloadSSLWithProgressTwisted(url, file, progress_func, privateKeyFileName, certificateFileName):
    """
    Can download from HTTPS sites.
    """
    global _UserAgentString
    from twisted.internet import ssl
    scheme, host, port, path = parse_url(url)
    factory = HTTPProgressDownloader(url, file, progress_func, agent=_UserAgentString)
    if scheme != 'https':
        return None
    contextFactory = ssl.DefaultOpenSSLContextFactory(privateKeyFileName, certificateFileName)
    reactor.connectSSL(host, port, factory, contextFactory)
    return factory.deferred


#-------------------------------------------------------------------------------


def downloadSSL(url, fileOrName, progress_func, certificates_filenames):
    """
    Another method to download from HTTPS.
    """
    global _UserAgentString
    from twisted.internet import ssl
    from OpenSSL import SSL

    class MyClientContextFactory(ssl.ClientContextFactory):
    
        def __init__(self, certificates_filenames):
            self.certificates_filenames = list(certificates_filenames)
    
        def verify(self, connection, x509, errnum, errdepth, ok):
            return ok
    
        def getContext(self):
            ctx = ssl.ClientContextFactory.getContext(self)
            for cert in self.certificates_filenames:
                try:
                    ctx.load_verify_locations(cert)
                except:
                    pass
            ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, self.verify)
            return ctx
    
    scheme, host, port, path = parse_url(url)
    if not isinstance(certificates_filenames, list):
        certificates_filenames = [certificates_filenames, ]
    cert_found = False
    for cert in certificates_filenames:
        if os.path.isfile(cert) and os.access(cert, os.R_OK):
            cert_found = True
            break
    if not cert_found:
        return fail(Exception('no one ssl certificate found'))
    
    factory = HTTPDownloader(url, fileOrName, agent=_UserAgentString)
    contextFactory = MyClientContextFactory(certificates_filenames)
    reactor.connectSSL(host, port, factory, contextFactory)
    return factory.deferred

#------------------------------------------------------------------------------


# class ProxyClientFactory(client.HTTPClientFactory):
# 
#     def setURL(self, url):
#         client.HTTPClientFactory.setURL(self, url)
#         self.path = url


def readResponse(response):
#     print('Response version:', response.version)
#     print('Response code:', response.code)
#     print('Response phrase:', response.phrase)
#     print('Response headers:')
#     print(list(response.headers.getAllRawHeaders()))
    if response.code != 200:
        return fail(Exception('Bad response from the server: [%d] %s' % (
            response.code, response.phrase.strip(),)))
    d = readBody(response)
    return d


def getPageTwisted(url, timeout=10, method=b'GET'):
    """
    A smart way to download pages from HTTP hosts.
    """
#     def getPageTwistedTimeout(_d):
#         _d.cancel()
#     def getPageTwistedTimeoutDisconnect(_tcpcall):
#         _tcpcall.disconnect()
#     def getPageTwistedCancelTimeout(x, _t):
#         if _t.active():
#             _t.cancel()
#         return x
    global _UserAgentString

    if not isinstance(url, six.binary_type):
        url = url.encode('utf-8')

#     if proxy_is_on():
#         factory = ProxyClientFactory(url, agent=_UserAgentString, timeout=timeout)
#         tcp_call = reactor.connectTCP(get_proxy_host(), get_proxy_port(), factory)
# #         if timeout:
# #             timeout_call = reactor.callLater(timeout, getPageTwistedTimeoutDisconnect, tcp_call)
# #             factory.deferred.addBoth(getPageTwistedCancelTimeout, timeout_call)
#         factory.deferred.addCallback(ConnectionDone, 'http', 'getPageTwisted proxy %s' % (url))
#         factory.deferred.addErrback(ConnectionFailed, 'http', 'getPageTwisted proxy %s' % (url))
#         return factory.deferred

    agent = Agent(reactor, connectTimeout=timeout)
    
    d = agent.request(
        method=method,
        uri=url,
        headers=Headers({b'User-Agent': [_UserAgentString, ]}),
    )
#     d = getPage(url, agent=_UserAgentString, timeout=timeout)
#     if timeout:
#         timeout_call = reactor.callLater(timeout, getPageTwistedTimeout, d)
#         d.addBoth(getPageTwistedCancelTimeout, timeout_call)
    d.addCallback(ConnectionDone, 'http', 'getPageTwisted %r' % url)
    d.addErrback(ConnectionFailed, 'http', 'getPageTwisted %r' % url)
    d.addCallback(readResponse)
    return d

#------------------------------------------------------------------------------


def downloadHTTP(url, fileOrName):
    """
    Another method to download from HTTP host.
    """
    global _UserAgentString
    scheme, host, port, path = parse_url(url)
    factory = HTTPDownloader(url, fileOrName, agent=_UserAgentString)
    if proxy_is_on():
        host = get_proxy_host()
        port = get_proxy_port()
        factory.path = url
    reactor.connectTCP(host, port, factory)
    return factory.deferred

#-------------------------------------------------------------------------------


def IpIsLocal(ip):
    """
    A set of "classic" patterns for local networks.
    """
    if not ip:
        return True
    if ip == '0.0.0.0':
        return True
    if ip.startswith('192.168.'):
        return True
    if ip.startswith('10.'):
        return True
    if ip.startswith('127.'):
        return True
    if ip.startswith('172.'):
        try:
            secondByte = int(ip.split('.')[1])
        except:
            raise Exception('wrong ip address ' + str(ip))
            return True
        if secondByte >= 16 and secondByte <= 31:
            return True
    return False

#-------------------------------------------------------------------------------


def getLocalIp():
    """
    A stack of methods to get the local IP of that machine.

    Had this in p2p/stun.py.
    http://ubuntuforums.org/showthread.php?t=1215042
    1. Use the gethostname method
    2. Use outside connection
    3. Use OS specific command
    4. Return 127.0.0.1 in unknown situation
    """
    # 1: Use the gethostname method

    try:
        ipaddr = socket.gethostbyname(socket.gethostname())
        if not(ipaddr.startswith('127')):
            #print('Can use Method 1: ' + ipaddr)
            return ipaddr
    except:
        pass

    # 2: Use outside connection
    '''
    Source:
    http://commandline.org.uk/python/how-to-find-out-ip-address-in-python/
    '''

    ipaddr = ''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('google.com', 0))
        ipaddr = s.getsockname()[0]
        #print('Can used Method 2: ' + ipaddr)
        return ipaddr
    except:
        pass

    # 3: Use OS specific command
    ipaddr = ''
    os_str = platform.system().upper()

    if os_str == 'LINUX':

        # Linux:
        arg = '`which ip` route list'
        p = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
        data = p.communicate()
        sdata = data[0].split()
        ipaddr = sdata[sdata.index('src') + 1]
        #netdev = sdata[ sdata.index('dev')+1 ]
        #print('Can used Method 3: ' + ipaddr)
        return ipaddr

    elif os_str == 'WINDOWS':

        # Windows:
        arg = 'route print 0.0.0.0'
        p = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
        data = p.communicate()
        strdata = data[0].decode()
        sdata = strdata.split()

        while len(sdata) > 0:
            if sdata.pop(0) == 'Netmask':
                if sdata[0] == 'Gateway' and sdata[1] == 'Interface':
                    ipaddr = sdata[6]
                    break
        #print('Can used Method 4: ' + ipaddr)
        return ipaddr

    return '127.0.0.1'  # uh oh, we're in trouble, but don't want to return none

#-------------------------------------------------------------------------------


def TestInternetConnectionOld(remote_host='www.google.com'):  # 74.125.113.99
    """
    Ancient method to check Internet connection.
    """
    try:
        (family, socktype, proto, garbage, address) = socket.getaddrinfo(remote_host, "http")[0]
    except Exception as e:
        return False

    s = socket.socket(family, socktype, proto)

    try:
        result = s.connect(address)
    except Exception as e:
        return False

    return result is None or result == 0

#------------------------------------------------------------------------------


def TestInternetConnectionOld2(remote_hosts=None, timeout=10):
    """
    A little bit more smart method to check Internet connection.
    """
    if remote_hosts is None:
        remote_hosts = []
        remote_hosts.append('www.google.com')
        remote_hosts.append('www.facebook.com')
        remote_hosts.append('www.youtube.com')
        # remote_hosts.append('www.yahoo.com')
        # remote_hosts.append('www.baidu.com')

    def _response(src, result):
        # print '_response', err, hosts, index
        result.callback(None)

    def _fail(err, hosts, index, result):
        # print 'fail', hosts, index
        reactor.callLater(0, _call, hosts, index + 1, result)

    def _call(hosts, index, result):
        # print 'call' , hosts, index, result
        if index >= len(hosts):
            result.errback(None)
            return
        # print '    ', hosts[index]
        d = getPageTwisted(hosts[index])
        d.addCallback(_response, result)
        d.addErrback(_fail, hosts, index, result)
    result = Deferred()
    reactor.callLater(0, _call, remote_hosts, 0, result)
    return result

#------------------------------------------------------------------------------


def TestInternetConnection(remote_hosts=None, timeout=10):
    """
    """
    if remote_hosts is None:
        remote_hosts = []
        from userid import known_servers
        for host, ports in known_servers.by_host().items():
            remote_hosts.append('http://%s:%d' % (host, ports[0], ))
    random.shuffle(remote_hosts)
    dl = []
    for host in remote_hosts[:5]:
        dl.append(getPageTwisted(host, timeout=timeout))
    return DeferredList(dl, fireOnOneCallback=True, fireOnOneErrback=False, consumeErrors=True)

#------------------------------------------------------------------------------


def SendEmail(TO, FROM, HOST, PORT, LOGIN, PASSWORD, SUBJECT, BODY, FILES):
    """
    Can send a email to SMTP server.
    """
#    try:
    import smtplib
    from email import Encoders
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.Utils import formatdate

    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = TO
    msg["Subject"] = SUBJECT
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(BODY))

    # attach a file
    for filePath in FILES:
        if not os.path.isfile(filePath):
            continue
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(filePath, "rb").read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filePath))
        msg.attach(part)

    s = smtplib.SMTP(HOST, PORT)

    # s.set_debuglevel(True) # It's nice to see what's going on

    s.ehlo()  # identify ourselves, prompting server for supported features

    if s.has_extn('STARTTLS'):
        s.starttls()
        s.ehlo()  # re-identify ourse

    s.login(LOGIN, PASSWORD)  # optional

    failed = s.sendmail(FROM, TO, msg.as_string())

    s.close()

#    except:
#        lg.exc()


#-------------------------------------------------------------------------------

def uploadHTTP(url, files, data, progress=None, receiverDeferred=None):
    """
    A smart way to upload a file over HTTP POST method.

    Use ``MultiPartProducer`` and ``StringReceiver`` classes.
    Great Thanks to Mariano!

    http://marianoiglesias.com.ar/python/file-uploading-with-multi-part-encoding-using-twisted/
    """
    
    class StringReceiver(protocol.Protocol):
        buffer = ""
    
        def __init__(self, deferred=None):
            self._deferred = deferred
    
        def dataReceived(self, data):
            self.buffer += data
    
        def connectionLost(self, reason):
            if self._deferred and reason.check(client.ResponseDone):
                self._deferred.callback(self.buffer)
            else:
                self._deferred.errback(Exception(self.buffer))


    @implementer(iweb.IBodyProducer)
    class MultiPartProducer:

        CHUNK_SIZE = 2 ** 8
    
        def __init__(self, files={}, data={}, callback=None, deferred=None):
            self._files = files
            self._file_lengths = {}
            self._data = data
            self._callback = callback
            self._deferred = deferred
            self.boundary = self._boundary()
            self.length = self._length()
    
        def startProducing(self, consumer):
            self._consumer = consumer
            self._current_deferred = Deferred()
            self._sent = 0
            self._paused = False
            if not hasattr(self, "_chunk_headers"):
                self._build_chunk_headers()
            if self._data:
                block = ""
                for field in self._data:
                    block += self._chunk_headers[field]
                    block += self._data[field]
                    block += "\r\n"
                self._send_to_consumer(block)
            if self._files:
                self._files_iterator = six.iterkeys(self._files)
                self._files_sent = 0
                self._files_length = len(self._files)
                self._current_file_path = None
                self._current_file_handle = None
                self._current_file_length = None
                self._current_file_sent = 0
                result = self._produce()
                if result:
                    return result
            else:
                return succeed(None)
            return self._current_deferred
    
        def resumeProducing(self):
            self._paused = False
            result = self._produce()
            if result:
                return result
    
        def pauseProducing(self):
            self._paused = True
    
        def stopProducing(self):
            self._finish(True)
            if self._deferred and self._sent < self.length:
                self._deferred.errback(Exception("Consumer asked to stop production of request body (%d sent out of %d)" % (self._sent, self.length)))
    
        def _produce(self):
            if self._paused:
                return
            done = False
            while not done and not self._paused:
                if not self._current_file_handle:
                    field = next(self._files_iterator)
                    self._current_file_path = self._files[field]
                    self._current_file_sent = 0
                    self._current_file_length = self._file_lengths[field]
                    self._current_file_handle = open(self._current_file_path, "rb")
                    self._send_to_consumer(self._chunk_headers[field])
                chunk = self._current_file_handle.read(self.CHUNK_SIZE)
                if chunk:
                    self._send_to_consumer(chunk)
                    self._current_file_sent += len(chunk)
                if not chunk or self._current_file_sent == self._current_file_length:
                    self._send_to_consumer("\r\n")
                    self._current_file_handle.close()
                    self._current_file_handle = None
                    self._current_file_sent = 0
                    self._current_file_path = None
                    self._files_sent += 1
                if self._files_sent == self._files_length:
                    done = True
            if done:
                self._send_to_consumer("--%s--\r\n" % self.boundary)
                self._finish()
                return succeed(None)
    
        def _finish(self, forced=False):
            if hasattr(self, "_current_file_handle") and self._current_file_handle:
                self._current_file_handle.close()
            if self._current_deferred:
                self._current_deferred.callback(self._sent)
                self._current_deferred = None
            if not forced and self._deferred:
                self._deferred.callback(self._sent)
    
        def _send_to_consumer(self, block):
            self._consumer.write(block)
            self._sent += len(block)
            if self._callback:
                self._callback(self._sent, self.length)
    
        def _length(self):
            self._build_chunk_headers()
            length = 0
            if self._data:
                for field in self._data:
                    length += len(self._chunk_headers[field])
                    length += len(self._data[field])
                    length += 2
            if self._files:
                for field in self._files:
                    length += len(self._chunk_headers[field])
                    length += self._file_size(field)
                    length += 2
            length += len(self.boundary)
            length += 6
            return length
    
        def _build_chunk_headers(self):
            if hasattr(self, "_chunk_headers") and self._chunk_headers:
                return
            self._chunk_headers = {}
            for field in self._files:
                self._chunk_headers[field] = self._headers(field, True)
            for field in self._data:
                self._chunk_headers[field] = self._headers(field)
    
        def _headers(self, name, is_file=False):
            value = self._files[name] if is_file else self._data[name]
            _boundary = self.boundary.encode("utf-8") if isinstance(self.boundary, six.text_type) else six.moves.urllib.parse.quote_plus(self.boundary)
            headers = ["--%s" % _boundary]
            if is_file:
                disposition = 'form-data; name="%s"; filename="%s"' % (name, os.path.basename(value))
            else:
                disposition = 'form-data; name="%s"' % name
            headers.append("Content-Disposition: %s" % disposition)
            if is_file:
                file_type = self._file_type(name)
            else:
                file_type = "text/plain; charset=utf-8"
            headers.append("Content-Type: %s" % file_type)
            if is_file:
                headers.append("Content-Length: %i" % self._file_size(name))
            else:
                headers.append("Content-Length: %i" % len(value))
            headers.append("")
            headers.append("")
            return "\r\n".join(headers)
    
        def _boundary(self):
            boundary = None
            try:
                import uuid
                boundary = uuid.uuid4().hex
            except ImportError:
                import random
                import sha
                bits = random.getrandbits(160)
                boundary = sha.new(str(bits).encode()).hexdigest()
            return boundary
    
        def _file_type(self, field):
            typ = mimetypes.guess_type(self._files[field])[0]
            return typ.encode("utf-8") if isinstance(typ, six.text_type) else str(typ)
    
        def _file_size(self, field):
            size = 0
            try:
                handle = open(self._files[field], "r")
                size = os.fstat(handle.fileno()).st_size
                handle.close()
            except:
                size = 0
            self._file_lengths[field] = size
            return self._file_lengths[field]

    # producerDeferred = Deferred()
    receiverDeferred = Deferred()

    myProducer = MultiPartProducer(files, data, progress)  # , producerDeferred)
    myReceiver = StringReceiver(receiverDeferred)

    headers = http_headers.Headers()
    headers.addRawHeader("Content-Type", "multipart/form-data; boundary=%s" % myProducer.boundary)

    agent = client.Agent(reactor)
    request = agent.request("POST", url, headers, myProducer)
    request.addCallback(lambda response: response.deliverBody(myReceiver))
    return request

#------------------------------------------------------------------------------


def getIfconfig(iface='en0'):
    try:
        result = subprocess.check_output(
            'ifconfig %s | grep -w inet' % (iface),
            shell=True, stderr=subprocess.STDOUT
        )
    except:
        return None
    ip = ''
    if result:
        strs = result.split(b'\n')
        for line in strs:
            # remove \t, space...
            line = line.strip()
            if line.startswith(b'inet '):
                a = line.find(b' ')
                ipStart = a + 1
                ipEnd = line.find(b' ', ipStart)
                if a != -1 and ipEnd != -1:
                    ip = line[ipStart:ipEnd]
                    break
    return ip


def getNetworkInterfaces():
    """
    Return a list of IPs for current active network interfaces.
    """
    plat = platform.uname()[0]

    if plat == 'Windows':
        dirs = ['', r'c:\windows\system32', r'c:\winnt\system32']
        try:
            import ctypes
            buffer = ctypes.create_string_buffer(300)
            ctypes.windll.kernel32.GetSystemDirectoryA(buffer, 300)
            dirs.insert(0, buffer.value.decode('mbcs'))
        except:
            pass
        for sysdir in dirs:
            try:
                pipe = os.popen(os.path.join(sysdir, 'ipconfig') + ' /all')
            except IOError:
                return []
            rawtxt = six.text_type(pipe.read())
            ips_unicode = re.findall(u'^.*?IP.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*$', rawtxt, re.U | re.M)
            ips = []
            for ip in ips_unicode:
                ips.append(str(ip))
            del ips_unicode
            return ips

    elif plat == 'Linux':
        try:
            pipe = os.popen("`which ip` -f inet a")
        except IOError:
            return []
        try:
            rawtxt = six.text_type(pipe.read())
            lines = rawtxt.splitlines()
        except:
            return []
        ips = set()
        for line in lines:
            check = line.strip('\n').strip().split(' ')
            if check[0] == "inet":
                if check[2] == "brd":
                    check.pop(2)
                    check.pop(2)
                ipaddress = check[1].split("/")[0]
                ips.add(str(ipaddress))
        return list(ips)

    elif plat == 'Darwin':
        try:
            # TODO: try to avoid socket connect to remote host
            return [_f for _f in [
                l for l in (
                    [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1],
                    # TODO: replace 8.8.8.8 with random seed node
                    [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]],
                ) if l
            ][0] if _f]
        except:
            eth0 = getIfconfig('eth0')
            en0 = getIfconfig('en0')
            return [_f for _f in [en0 or eth0, ] if _f]
