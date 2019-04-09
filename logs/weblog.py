#!/usr/bin/python
# weblog.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (weblog.py) is part of BitDust Software.
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
#

"""
.. module:: weblog.

A useful code to monitor program logs in the Web browser using local
HTML server.
"""

from __future__ import absolute_import
import sys
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import base64
from time import strftime
from six.moves import range

try:
    from twisted.internet import reactor  # @UnresolvedImport
except:
    sys.exit('Error initializing twisted.internet.reactor in weblog.py')

from twisted.web import server, resource

#------------------------------------------------------------------------------

myweblistener = None
default_level = 6
default_reload_timeout = 600
default_lines = 9999
maxlines = default_lines
numlines = 0
logtext = ''
lineindex = 0

header_html = '''<html><head>
<meta http-equiv="refresh" content="%(reload)s">
<title>Logs</title></head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#0000FF">
<form action="" method="get">
<input size="4" name="level" value="%(level)s" />
<input size="4" name="reload" value="%(reload)s" />
<input size="10" name="lines" value="%(lines)s" />
<input type="submit" value="update" />
</form>
<a href="?reload=0.2&level=%(level)s&lines=%(lines)s">[1/5 sec.]</a>|
<a href="?reload=0.5&level=%(level)s&lines=%(lines)s">[1/2 sec.]</a>|
<a href="?reload=1&level=%(level)s&lines=%(lines)s">[1 sec.]</a>|
<a href="?reload=5&level=%(level)s&lines=%(lines)s">[5 sec.]</a>|
<a href="?reload=10&level=%(level)s&lines=%(lines)s">[10 sec.]</a>|
<a href="?reload=30&level=%(level)s&lines=%(lines)s">[30 sec.]</a>|
<a href="?reload=600&level=%(level)s&lines=%(lines)s">[600 sec.]</a>
<br>
<a href="?level=2&reload=%(reload)s&lines=%(lines)s">[debug2]</a>|
<a href="?level=4&reload=%(reload)s&lines=%(lines)s">[debug4]</a>|
<a href="?level=6&reload=%(reload)s&lines=%(lines)s">[debug6]</a>|
<a href="?level=8&reload=%(reload)s&lines=%(lines)s">[debug8]</a>|
<a href="?level=10&reload=%(reload)s&lines=%(lines)s">[debug10]</a>|
<a href="?level=12&reload=%(reload)s&lines=%(lines)s">[debug12]</a>|
<a href="?level=18&reload=%(reload)s&lines=%(lines)s">[debug18]</a>
<a href="?level=99&reload=%(reload)s&lines=%(lines)s">[debug99]</a>
<pre>
'''

level2color = {
    0: '',
    1: '',
    2: '',
    3: '',
    4: '#404040',
    5: '#404040',
    6: '#606060',
    7: '#606060',
    8: '#808080',
    9: '#808080',
    10: '#A0A0A0',
    11: '#A0A0A0',
    12: '#B0B0B0',
    13: '#B0B0B0',
    14: '#C0C0C0',
    15: '#C0C0C0',
    16: '#D0D0D0',
    17: '#D0D0D0',
    18: '#D0D0D0',
    19: '#D0D0D0',
    20: '#D0D0D0',
    21: '#D0D0D0',
    22: '#D0D0D0',
    23: '#D0D0D0',
}

#------------------------------------------------------------------------------


def init(port=9999):
    global myweblistener
    if myweblistener:
        return
    from logs import lg
    root = RootResource()
    site = server.Site(root)
    try:
        myweblistener = reactor.listenTCP(port, site)
    except:
        lg.exc()
        return
    lg.set_weblog_func(log)


def shutdown():
    global myweblistener
    if myweblistener:
        myweblistener.stopListening()
        del myweblistener
        myweblistener = None

#------------------------------------------------------------------------------


def log(level, s):
    global logtext
    global maxlines
    global numlines
    global lineindex
    global myweblistener
    if not myweblistener:
        return
    logtext += '%d|%d|%s|%s\n' % (lineindex, level, strftime('%H:%M:%S'), s.replace('\n', '#nl'))
    numlines += 1
    lineindex += 1
    while numlines > maxlines:
        logtext = logtext[logtext.find('\n') + 1:]
        numlines -= 1

#------------------------------------------------------------------------------


class LogPage(resource.Resource):

    def __init__(self, parent):
        self.parent = parent
        resource.Resource.__init__(self)

    def render(self, request):
        global logtext
        global maxlines
        DlevelS = request.args.get('level', [''])[0]
        try:
            DlevelV = int(DlevelS)
        except:
            DlevelV = default_level

        reloadS = request.args.get('reload', [''])[0]
        try:
            reloadV = float(reloadS)
        except:
            reloadV = default_reload_timeout

        linesS = request.args.get('lines', [''])[0]
        try:
            maxlines = int(linesS)
        except:
            maxlines = default_lines

        d = {'level': str(DlevelV), 'reload': str(reloadV), 'lines': str(maxlines)}
        out = header_html % d
        all_lines = logtext.splitlines()
        for lineindex in range(len(all_lines) - 1, -1, -1):
            line = all_lines[lineindex]
            t = line.split('|')
            try:
                #lineindex = int(t[0])
                level = int(t[1])
                timestr = t[2]
                s = ''.join(t[3:])
            except:
                #lineindex = 0
                level = 0
                timestr = ''
                s = line
            if level > DlevelV:
                continue

            s = s.strip().replace('#nl', '\n')
            s = ('%6d' % lineindex) + ' ' + timestr + (' ' * level) + ' ' + s

            textcolor = level2color.get(level, '')
            color = ''
            if s.find('BOGUS') > 0:
                color = 'purple'
                textcolor = 'white'
            if s.find('WARNING') > 0:
                color = '#FFFC75'
                textcolor = 'black'
            if s.find('ERROR') > 0:
                color = 'red'
                textcolor = 'white'
            if s.find('NETERROR') > 0:
                color = 'gray'
                textcolor = 'white'
            if s.find('Exception:') > 0:
                color = 'red'
                textcolor = 'white'
            if s.find(' <<< ') > 0:
                color = '#B2B2FF'
                textcolor = 'black'
            if s.find(' >>> ') > 0:
                color = '#88ff88'
                textcolor = 'black'
            if s.find(' << ') > 0:
                color = '#ccccff'
                textcolor = 'black'
            if s.find(' >> ') > 0:
                if s.find(' failed ') > 0:
                    color = '#ffdddd'
                else:
                    color = '#ccffcc'
                textcolor = 'black'

            a = '%s'
            if color != '':
                a = ('<font color="%s" style="BACKGROUND-COLOR:%s">' % (textcolor, color)) + '%s</font>'
            elif textcolor != '':
                a = ('<font color="%s">' % textcolor) + '%s</font>'
            if level <= 4:
                a = '<b>%s</b>' % a

            s = s.replace('>', '&gt;').replace('<', '&lt;')

            try:
                out += a % str(s)
            except:
                try:
                    out += a % str(six.moves.urllib.parse.quote(s))
                except:
                    out += a % str(base64.encodestring(s))

        return out + '</pre></body></html>'

#------------------------------------------------------------------------------


class RootResource(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        logpage = LogPage(self)
        self.putChild('', logpage)

#------------------------------------------------------------------------------

if __name__ == "__main__":
    init(int(sys.argv[1]))
    reactor.run()
