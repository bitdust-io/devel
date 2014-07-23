#!/usr/bin/python
#webtraffic.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: webtraffic

A useful code to monitor program packets traffic in the Web browser using local HTML server. 
"""

import sys

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in trafficstats.py')

from twisted.web import server, resource

#-------------------------------------------------------------------------------

#(total bytes, finished packets, failed packets, total packets)
_InboxPacketsCount = 0
_InboxByIDURL = {}
_InboxByHost = {}
_InboxByProto = {}
_InboxByType = {}

_OutboxPacketsCount = 0
_OutboxByIDURL = {}
_OutboxByHost = {}
_OutboxByProto = {}
_OutboxByType = {}

_WebListener = None

_DefaultReloadTimeout = 600

#-------------------------------------------------------------------------------

def init(root=None, path='traffic', port=9997):
    global _WebListener
    if root is not None:
        from transport import callback
        callback.add_inbox_callback(inbox)
        callback.add_finish_file_sending_callback(outbox)
        root.putChild(path, TrafficPage())
        return
    if _WebListener:
        return
    root = resource.Resource()
    root.putChild('', TrafficPage())
    site = server.Site(root)
    try:
        _WebListener = reactor.listenTCP(port, site)
    except:
        from logs import lg
        lg.exc()
        return
    from transport import callback
    callback.add_inbox_callback(inbox)
    callback.add_finish_file_sending_callback(outbox)

def shutdown():
    global _WebListener
    if _WebListener:
        _WebListener.stopListening()
        del _WebListener
        _WebListener = None

def inbox_packets_count():
    global _InboxPacketsCount
    return _InboxPacketsCount
    
def inbox_by_idurl():
    global _InboxByIDURL
    return _InboxByIDURL
    
def inbox_by_host():
    global _InboxByHost
    return _InboxByHost
    
def inbox_by_proto():
    global _InboxByProto
    return _InboxByProto

def inbox_by_type():
    global _InboxByType
    return _InboxByType
    
def outbox_packets_count():
    global _OutboxPacketsCount
    return _OutboxPacketsCount
    
def outbox_by_idurl():
    global _OutboxByIDURL
    return _OutboxByIDURL
    
def outbox_by_host():
    global _OutboxByHost
    return _OutboxByHost
    
def outbox_by_proto(): 
    global _OutboxByProto
    return _OutboxByProto

def outbox_by_type():
    global _OutboxByType
    return _OutboxByType

def inbox(newpacket, info, status, error_message):
    global _InboxPacketsCount
    global _InboxByIDURL
    global _InboxByHost
    global _InboxByProto
    global _InboxByType
    
    if newpacket is None:
        return

    byts = len(newpacket)
    idurl = newpacket.CreatorID
    host = '%s://%s' % (info.proto, info.host)
    typ = newpacket.Command

    if not _InboxByIDURL.has_key(idurl):
        _InboxByIDURL[idurl] = [0, 0, 0, 0]
    _InboxByIDURL[idurl][0] += byts
    if status == 'finished':
        _InboxByIDURL[idurl][1] += 1
    else:
        _InboxByIDURL[idurl][2] += 1
    _InboxByIDURL[idurl][3] += 1

    if not _InboxByHost.has_key(host):
        _InboxByHost[host] = [0, 0, 0, 0]
    _InboxByHost[host][0] += byts
    if status == 'finished':
        _InboxByHost[host][1] += 1
    else:
        _InboxByHost[host][2] += 1
    _InboxByHost[host][3] += 1

    if not _InboxByProto.has_key(info.proto):
        _InboxByProto[info.proto] = [0, 0, 0, 0]
    _InboxByProto[info.proto][0] += byts
    if status == 'finished':
        _InboxByProto[info.proto][1] += 1
    else:
        _InboxByProto[info.proto][2] += 1
    _InboxByProto[info.proto][3] += 1
    
    if not _InboxByType.has_key(typ):
        _InboxByType[typ] = [0, 0, 0, 0]
    _InboxByType[typ][0] += byts
    if status == 'finished':
        _InboxByType[typ][1] += 1
    else:
        _InboxByType[typ][2] += 1
    _InboxByType[typ][3] += 1

    _InboxPacketsCount += 1

def outbox(pkt_out, item, status, size, error_message):
    global _OutboxPacketsCount
    global _OutboxByIDURL
    global _OutboxByHost
    global _OutboxByProto
    global _OutboxByType

    byts = pkt_out.filesize
    idurl = pkt_out.remote_idurl
    host = '%s://%s' % (item.proto, item.host)
    typ = pkt_out.outpacket.Command

    if not _OutboxByIDURL.has_key(idurl):
        _OutboxByIDURL[idurl] = [0, 0, 0, 0]
    _OutboxByIDURL[idurl][0] += byts
    if status == 'finished':
        _OutboxByIDURL[idurl][1] += 1
    else:
        _OutboxByIDURL[idurl][2] += 1
    _OutboxByIDURL[idurl][3] += 1

    if not _OutboxByHost.has_key(host):
        _OutboxByHost[host] = [0, 0, 0, 0]
    _OutboxByHost[host][0] += byts
    if status == 'finished':
        _OutboxByHost[host][1] += 1
    else:
        _OutboxByHost[host][2] += 1
    _OutboxByHost[host][3] += 1

    if not _OutboxByProto.has_key(item.proto):
        _OutboxByProto[item.proto] = [0, 0, 0, 0]
    _OutboxByProto[item.proto][0] += byts
    if status == 'finished':
        _OutboxByProto[item.proto][1] += 1
    else:
        _OutboxByProto[item.proto][2] += 1
    _OutboxByProto[item.proto][3] += 1

    if not _OutboxByType.has_key(typ):
        _OutboxByType[typ] = [0, 0, 0, 0]
    _OutboxByType[typ][0] += byts
    if status == 'finished':
        _OutboxByType[typ][1] += 1
    else:
        _OutboxByType[typ][2] += 1
    _OutboxByType[typ][3] += 1

    _OutboxPacketsCount += 1

#-------------------------------------------------------------------------------

class TrafficPage(resource.Resource):
    header_html = '''<html><head>
<meta http-equiv="refresh" content="%(reload)s">
<title>Traffic</title></head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#0000FF">
<form action="%(baseurl)s?" method="get">
<input size="4" name="reload" value="%(reload)s" />
<input type="submit" value="update" />
</form>
<a href="%(baseurl)s?reload=1&type=%(type)s&dir=%(dir)s">[1 sec.]</a>|
<a href="%(baseurl)s?reload=5&type=%(type)s&dir=%(dir)s">[5 sec.]</a>|
<a href="%(baseurl)s?reload=10&type=%(type)s&dir=%(dir)s">[10 sec.]</a>|
<a href="%(baseurl)s?reload=60&type=%(type)s&dir=%(dir)s">[60 sec.]</a>
<br>
<a href="%(baseurl)s?type=idurl&reload=%(reload)s&dir=%(dir)s">[by idurl]</a>|
<a href="%(baseurl)s?type=host&reload=%(reload)s&dir=%(dir)s">[by host]</a>|
<a href="%(baseurl)s?type=proto&reload=%(reload)s&dir=%(dir)s">[by proto]</a>
<a href="%(baseurl)s?type=type&reload=%(reload)s&dir=%(dir)s">[by type]</a>
<br>
<a href="%(baseurl)s?type=%(type)s&reload=%(reload)s&dir=in">[income traffic]</a>|
<a href="%(baseurl)s?type=%(type)s&reload=%(reload)s&dir=out">[outgoing traffic]</a>
<br>
<table><tr>
<td align=left>%(type)s
<td>total bytes
<td>total packets
<td>finished packets
<td>failed packets
'''

    def render(self, request):
        global _InboxPacketsCount
        global _InboxByIDURL
        global _InboxByHost
        global _InboxByProto
        global _OutboxPacketsCount
        global _OutboxByIDURL
        global _OutboxByHost
        global _OutboxByProto

        direction = request.args.get('dir', [''])[0]
        if direction not in ('in', 'out'):
            direction = 'in'
        typ = request.args.get('type', [''])[0]
        if typ not in ('idurl', 'host', 'proto', 'type'):
            typ = 'idurl'
        reloadS = request.args.get('reload', [''])[0]
        try:
            reloadV = int(reloadS)
        except:
            reloadV = _DefaultReloadTimeout

        d = {'type': typ, 'reload': str(reloadV), 'dir': direction, 'baseurl': request.path}
        out = self.header_html % d
        if direction == 'in':
            if typ == 'idurl':
                for i, v in _InboxByIDURL.items():
                    out += '<tr><td><a href="%s">%s</a><td>%d<td>%d<td>%d<td>%d\n' % (
                        i, i, v[0], v[3], v[1], v[2])
            elif typ == 'host':
                for i, v in _InboxByHost.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'proto':
                for i, v in _InboxByProto.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'type':
                for i, v in _InboxByType.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])
        else:
            if typ == 'idurl':
                for i, v in _OutboxByIDURL.items():
                    out += '<tr><td><a href="%s">%s</a><td>%d<td>%d<td>%d<td>%d\n' % (
                        i, i, v[0], v[3], v[1], v[2])
            elif typ == 'host':
                for i, v in _OutboxByHost.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'proto':
                for i, v in _OutboxByProto.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])
            elif typ == 'type':
                for i, v in _OutboxByType.items():
                    out += '<tr><td>%s<td>%d<td>%d<td>%d<td>%d\n' % (
                        i, v[0], v[3], v[1], v[2])

        out += '</table>'
        if direction == 'in':
            out += '<p>total income packets: %d</p>' % _InboxPacketsCount
        else:
            out += '<p>total outgoing packets: %d</p>' % _OutboxPacketsCount
        out += '</body></html>'

        return out

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    init()
    reactor.run()

