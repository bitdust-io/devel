#!/usr/bin/python
#nameurl.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: nameurl

Here is a methods to work with URL strings.
We assume DHN URLs are of the form::

    ssh://host.name.com:port/fooobar.xml  (maybe no foobar.xml)
    tcp://123.45.67.89:4321
    dhtudp://veselin@my.identityserver.net:8080/some_folder/veselin
    
Tried built-in methods ``urlparse()`` and ``urlsplit()`` 
and they move the location from the second to the 3rd
argument if you have "http" vs "ssh" or "tcp".  
This seems like trouble.
"""

import re
import urllib
import urlparse

#------------------------------------------------------------------------------ 

legalchars="#.-_()ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
legalset= set(legalchars)

#------------------------------------------------------------------------------ 

def UrlParse(url):
    """
    Return a tuple of strings from url address : ( proto, host, port, filename )
        >>> import nameurl
        >>> nameurl.UrlParse('http://id.bitpie.net/veselin.xml')
        ('http', 'id.bitpie.net', '', 'veselin.xml')
    """
    o = urlparse.urlparse(url)
    proto = o.scheme.strip()
    base = o.netloc.lstrip(' /')
    filename = o.path.lstrip(' /')
    if base == '':
        base = o.path.lstrip(' /')
        filename = ''

    if base.find('/') < 0:
        if base.find(':') < 0:
            host = base
            port = ''
        else:
            host, port = base.split(':', 1)
    else:
        host, tail = base.split('/', 1)
        if host.find(':') < 0:
            port = ''
        else:
            host, port = host.split(':', 1)

        if filename == '':
            filename = tail
    
    return proto.strip(), host.strip(), port.strip(), filename.strip()


def UrlMake(protocol='', machine='', port='', filename='', parts=None):
    """
    Reverse method, create a URL from 4 pieces.
    """
    if parts is not None:
        protocol, machine, port, filename = parts
    url = protocol+'://'+machine
    if port != '':
        url += ':'+str(port)
    if filename != '':
        url += '/'+filename
    return url


def UrlFilename(url):
    """
    Generate a 'safe' filename from URL address.
    This is useful when need to store identity files on disk.
        >>> nameurl.UrlFilename('http://id.bitpie.net/veselin.xml')
        'http###id.bitpie.net#veselin.xml'     
    """
    if url is None:
        return None
    result = url.replace("://","###")
    result = result.replace("/","#")
    result = re.sub('(\:)(\d+)', '(#\g<2>#)', result)
    result = result.lower()
#    global legalset
#    # SECURITY  Test that all characters are legal ones
#    for x in result:
#        if x not in legalset:
#            raise Exception("nameurl.UrlFilename ERROR illegal character: \n" + url)
    return result


def FilenameUrl(filename):
    """
    A reverse method for ``UrlFilename()``.
    """
    src = filename.strip().lower()
    if not src.startswith('http###'):
        return None
    src = re.sub('\(#(\d+)#\)', ':\g<1>', src)
    src = 'http://' + src[7:].replace('#', '/')
    return str(src)


def UrlFilenameHTML(url):
    """
    Another method to simplify URL, so you can create a filename from URL string.
        >>> nameurl.UrlFilenameHTML('http://id.bitpie.net/veselin.xml')
        'identity_datahaven_net_veselin_xml'     
    """
    global legalset
    s = url.replace('http://', '')
    o = ''
    for x in s:
        if x not in legalset or x == '.' or x == ':' or x == '#':
            o += '_'
        else:
            o += x
    return o


def GetName(url):
    """
    Deal with the identities, return a filename (without extension) from URL address. 
        >>> nameurl.GetName('http://id.bitpie.net/kinggeorge.xml')
        'kinggeorge'    
    """
    if url in [None, 'None', '',]:
        return ''
    if not url.endswith('.xml'):
        return url        
    return url[url.rfind("/")+1:-4] #return url[url.rfind("/")+1:url.rfind(".")]


def GetFileName(url):
    """
    Almost the same, but keeps the file extension.
    """
    if url in [None, 'None', ]:
        return ''
    return url[url.rfind("/")+1:]

def Quote(s):
    """
    A wrapper for built-in method ``urllib.quote()``.
    """
    return urllib.quote(s, '')

def UnQuote(s):
    """
    A wrapper for built-in method ``urllib.unquote()``.
    """
    return urllib.unquote(s)

def IdContactSplit(contact):
    try:
        return contact.split('://')
    except:
        return '', '' 

#------------------------------------------------------------------------------ 

def main():
    """
    I used this place for tests.
    """
#    url = 'http://id.bitpie.net:565/sdfsdfsdf/veselin2.xml'
##    url = 'ssh://34.67.22.5: 5654 /gfgfg.sdfsdf/sdfsd'
##    url = 'q2q://d5wJMQRBYD72V6Zb5aZ1@work.offshore.ai'
##    print UrlParse(url)
#    print url
#    fn =  UrlFilename(url)
#    print fn
#    ur = FilenameUrl(fn)
#    print ur
##    print filenameurl
##    print FilenameUrl(filenameurl)
##    proto, machine, port, name = UrlParse(url)
##    url2 = UrlMake(proto, machine, 1234, name)
##    print url2
##    filenameurl2 = UrlFilename(url2)
##    print filenameurl2
##    print FilenameUrl(filenameurl2)
##    print UrlParse('q2q://d5wJMQRBYD72V6Zb5aZ1@work.offshore.ai')
    print GetName(str(None))

if __name__ == '__main__':
    main()










