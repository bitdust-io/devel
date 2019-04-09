#!/usr/bin/python
# nameurl.py
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (nameurl.py) is part of BitDust Software.
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
.. module:: nameurl.

Here is a methods to work with URL strings.
We assume BitDust URLs are of the form::

    ssh://host.name.com:port/fooobar.xml  (maybe no foobar.xml)
    tcp://123.45.67.89:4321
    udp://veselin@my.identityserver.net:8080/some_folder/veselin

Tried built-in methods ``urlparse()`` and ``urlsplit()``
and they move the location from the second to the 3rd
argument if you have "http" vs "ssh" or "tcp".
This seems like trouble.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import six.moves.urllib.parse
from six.moves import range

#------------------------------------------------------------------------------

import re

#------------------------------------------------------------------------------

from lib import strng

#------------------------------------------------------------------------------

legalchars = "#.-_()ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
legalset = set(legalchars)

#------------------------------------------------------------------------------


def UrlParse(url):
    """
    Return a tuple of strings from url address : ( proto, host, port, filename )
        import nameurl
        nameurl.UrlParse('http://id.bitdust.io/veselin.xml')
        ('http', 'id.bitdust.io', '', 'veselin.xml')
    """
    url = strng.to_bin(url)
    o = six.moves.urllib.parse.urlparse(url)
    proto = strng.to_bin(o.scheme.strip())
    base = strng.to_bin(o.netloc).lstrip(b' /')
    filename = strng.to_bin(o.path).lstrip(b' /')
    if not base:
        base = strng.to_bin(o.path).lstrip(b' /')
        filename = b''

    if base.find(b'/') < 0:
        if base.find(b':') < 0:
            host = base
            port = b''
        else:
            host, port = base.split(b':', 1)
    else:
        host, tail = base.split(b'/', 1)
        if host.find(b':') < 0:
            port = b''
        else:
            host, port = host.split(b':', 1)

        if not filename:
            filename = tail

    return (
        strng.to_text(proto).strip(),
        strng.to_text(host).strip(),
        strng.to_text(port).strip(),
        strng.to_text(filename).strip(),
    )


def UrlMake(protocol='', machine='', port='', filename='', parts=None):
    """
    Reverse method, create a URL from 4 pieces.
    """
    if parts is not None:
        protocol, machine, port, filename = parts
    url = protocol + '://' + strng.to_text(machine)
    if port:
        url += ':' + strng.to_text(port)
    if filename:
        url += '/' + filename
    return strng.to_bin(url)


def UrlFilename(url):
    """
    Generate a 'safe' filename from URL address.

    This is useful when need to store identity files on disk.
    nameurl.UrlFilename('http://id.bitdust.io/veselin.xml')
    'http###id.bitdust.io#veselin.xml'
    """
    # TODO: switch all that to global ID format
    if not url:
        return None
    result = strng.to_text(url)
    result = result.replace("://", "###")
    result = result.replace("/", "#")
    result = re.sub('(\:)(\d+)', '(#\g<2>#)', result)
    result = result.lower()
#    global legalset
#    # TODO:   SECURITY  Test that all characters are legal ones
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
    return strng.to_bin(src)


def UrlFilenameHTML(url):
    """
    Another method to simplify URL, so you can create a filename from URL
    string.

    nameurl.UrlFilenameHTML('http://id.bitdust.io/veselin.xml')
    'id_bitdust_net_veselin_xml'
    """
    global legalset
    url = strng.to_text(url)
    s = url.replace('http://', '')
    o = ''
    for x in s:
        if x not in legalset or x == '.' or x == ':' or x == '#':
            o += '_'
        else:
            o += x
    return o

#------------------------------------------------------------------------------

def IdContactSplit(contact):
    """
    """
    try:
        return strng.to_text(contact).split('://')
    except:
        return '', ''


def GetName(url):
    """
    Deal with the identities, return a filename (without extension) from URL
    address.

    nameurl.GetName('http://id.bitdust.io/kinggeorge.xml') 'kinggeorge'
    """
    if url in [None, 'None', '', b'None', b'', ]:
        return ''
    url = strng.to_text(url)
    if not url.endswith('.xml'):
        return url
    return url[url.rfind("/") + 1:-4]  # return url[url.rfind("/")+1:url.rfind(".")]


def GetFileName(url):
    """
    Almost the same, but keeps the file extension.
    """
    if url in [None, 'None', '', b'None', b'', ]:
        return ''
    url = strng.to_text(url)
    return url[url.rfind("/") + 1:]


def GetHost(url):
    """
    Return host name value from url.
    """
    return UrlParse(url)[1]

#------------------------------------------------------------------------------

def Quote(s):
    """
    A wrapper for built-in method ``urllib.quote()``.
    """
    return six.moves.urllib.parse.quote(s, '')


def UnQuote(s):
    """
    A wrapper for built-in method ``urllib.unquote()``.
    """
    return six.moves.urllib.parse.unquote(s)


#------------------------------------------------------------------------------

def DjangoQuote(s):
    """
    Ensure that primary key values do not confuse the admin URLs by escaping
    any '/', '_' and ':' and similarly problematic characters.

    Similar to urllib.quote, except that the quoting is slightly
    different so that it doesn't get automatically unquoted by the Web
    browser.
    """
    res = list(s)
    for i in range(len(res)):
        c = res[i]
        if c in """:/_#?;@&=+$,"<>%\\""":
            res[i] = '_%02X' % ord(c)
    return ''.join(res)


def DjangoUnQuote(s):
    """
    Undo the effects of quote().

    Based heavily on urllib.unquote().
    """
    mychr = chr
    myatoi = int
    lst = s.split('_')
    res = [lst[0]]
    myappend = res.append
    del lst[0]
    for item in lst:
        if item[1:2]:
            try:
                myappend(mychr(myatoi(item[:2], 16)) + item[2:])
            except ValueError:
                myappend('_' + item)
        else:
            myappend('_' + item)
    return "".join(res)

#------------------------------------------------------------------------------


def main():
    """
    I used this place for tests.
    """
    print(GetName(str(None)))

if __name__ == '__main__':
    main()
