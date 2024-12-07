"""
Apache2 config

<VirtualHost *:80>
        ServerName blockchain.bitdust.io
        ServerAlias www.blockchain.bitdust.io
        Redirect / https://blockchain.bitdust.io/
        RewriteEngine on
        RewriteCond %{SERVER_NAME} =blockchain.bitdust.io [OR]
        RewriteCond %{SERVER_NAME} =www.blockchain.bitdust.io
        RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>

<VirtualHost *:443>
        ServerName blockchain.bitdust.io
        ServerAlias www.blockchain.bitdust.io
        ServerAdmin bitdust.io@gmail.com
        DocumentRoot /var/www
        SSLEngine on
        RewriteEngine on
        RewriteRule ^/([a-zA-Z0-9]*)$ http://localhost:19080/$1 [P,L]
        SSLCertificateFile /ssl/domain.cert.pem
        SSLCertificateKeyFile /ssl/private.key.pem
</VirtualHost>
"""

import sys
import time
import sqlite3
import base64

#------------------------------------------------------------------------------

if __name__ == '__main__':
    import os.path as _p
    sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
    src_dir_path = _p.dirname(_p.dirname(_p.dirname(_p.abspath(sys.argv[0]))))
    sys.path.insert(0, src_dir_path)
    sys.path.insert(0, _p.join(src_dir_path, 'bitdust_forks', 'Bismuth'))

#------------------------------------------------------------------------------

from twisted.internet import reactor
from twisted.web import server, resource

#------------------------------------------------------------------------------

from bitdust.logs import lg

from bitdust.lib import strng
from bitdust.lib import misc

from bitdust.main import settings
from bitdust.main import config

from bitdust.interface import web_html_template

from bitdust.blockchain import bismuth_node

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

_DataDirPath = None
_ExplorerHost = None
_ExplorerPort = None
_WebListener = None

#------------------------------------------------------------------------------


def init():
    global _DataDirPath
    global _ExplorerHost
    global _ExplorerPort
    global _WebListener

    _DataDirPath = settings.ServiceDir('bismuth_blockchain')
    _ExplorerHost = config.conf().getString('services/blockchain-explorer/host', '127.0.0.1')
    _ExplorerPort = config.conf().getInt('services/blockchain-explorer/web-port', 19080)

    root = BlockchainRootPage()
    root.putChild(b'', BlockchainMainPage())
    try:
        _WebListener = reactor.listenTCP(_ExplorerPort, server.Site(root))  # @UndefinedVariable
        if _Debug:
            lg.out(_DebugLevel, '            have started web server at port %d   hostname=%s' % (_ExplorerPort, strng.to_text(_ExplorerHost)))
    except:
        if _Debug:
            lg.err('exception while trying to listen port ' + str(self.web_port))
        lg.exc()
    if _Debug:
        lg.args(_DebugLevel, data_dir_path=_DataDirPath)
    return True


def shutdown():
    global _WebListener
    if _Debug:
        lg.dbg(_DebugLevel, '')
    if _WebListener:
        _WebListener.stopListening()
        if _Debug:
            lg.out(_DebugLevel, '            stopped web listener')
    _WebListener = None
    return True


#------------------------------------------------------------------------------


def execute(cursor, query, param):
    while True:
        try:
            cursor.execute(query, param)
            break
        except Exception as e:
            print('Database query: {} {}'.format(cursor, query))
            print('Database retry reason: {}'.format(e))
            time.sleep(0.2)
    return cursor


#------------------------------------------------------------------------------


class BlockchainMainPage(resource.Resource):

    def render_GET(self, request):
        global _ExplorerHost

        page_size = 500

        page_num = request.args.get(b'page', [])
        if page_num:
            try:
                page_num = int(strng.to_text(page_num[0]))
            except:
                lg.exc()
                page_num = 0
        else:
            page_num = 0

        page_max = page_num + 1

        src = ''

        conn = sqlite3.connect(bismuth_node.nod().ledger_path, timeout=60.0)
        c = conn.cursor()
        execute(c, 'SELECT * FROM transactions ORDER BY block_height DESC, timestamp DESC LIMIT ? OFFSET ?;', (
            page_size,
            page_size*page_num,
        ))
        _all = c.fetchall()
        c.close()
        conn.close()
        conn = None
        c = None

        if len(_all) < page_size:
            page_max = page_num

        view = []
        b = -1
        x_old = 'init'

        for x in _all:
            if x[0] != x_old:
                color_cell = '#F8F8F8'
                if b >= 0:
                    view.append('<tr><td>&nbsp;</td></tr>')  #block separator
            else:
                color_cell = 'white'

            view.append('<tr bgcolor ={}>'.format(color_cell))

            if x[0] != x_old:
                b = b + 1

            txid_formatted = strng.to_text(base64.b64encode(strng.to_bin(x[5]), altchars=b'-_'))
            view.append('<td><a href="/{}">{}</a></td>'.format(
                txid_formatted,
                txid_formatted[:8],
            ))  #TXID

            view.append('<td>{}'.format(time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime(float(x[1])))))
            view.append('<td>{}</td>'.format(x[2][:8]))  #from
            view.append('<td>{}</td>'.format(x[3][:8]))  #to
            view.append('<td>{}</td>'.format(misc.float2str(x[4], mask='%10.12f')))  #amount

            if x_old != x[0]:
                view.append('<td>{}</td>'.format(x[7][:8]))  #block hash
            else:
                view.append('<td>&nbsp;</td>')  #block hash

            view.append('<td>{}</td>'.format(misc.float2str(x[8], mask='%10.12f')))  #fee
            view.append('<td>{}</td>'.format(misc.float2str(x[9], mask='%10.12f')))  #reward

            view.append('<td>{}{}</td>'.format(x[10][:16], '&hellip;' if len(x[10]) > 16 else ''))  #operation
            view.append('<td>{}{}</td>'.format(x[11][:24], '&hellip;' if len(x[11]) > 24 else ''))  #openfield

            if x_old != x[0]:
                view.append('<td>{}</td>'.format(x[0]))  #block height
            else:
                view.append('<td>{}</td>'.format(x[0]))  #block height

            view.append('</tr>')

            x_old = x[0]

        src += '<div id="ui-blockchain-explorer" class="section bg-light">'
        src += '<div class="container">\n'
        src += '<div class="ui-card">\n'
        src += '<div class="card-body">\n'

        src += '<div class="row justify-content-center">\n'
        src += '<h1 align=center>BitDust blockchain explorer</h1>\n'
        src += '</div>\n'

        src += '<div class="row justify-content-center">\n'
        src += '<ul class="pagination pagination-sm">\n'
        src += '<li class="page-item">\n'
        src += '<a class="page-link" href="/?page={}">\n'.format(max(0, page_num - 1))
        src += '<span aria-hidden="true">&laquo;</span>\n'
        src += '</a>\n'
        src += '</li>\n'
        src += '<li class="page-item">\n'
        src += '<a class="page-link" href="/?page={}">\n'.format(min(page_max, page_num + 1))
        src += '<span aria-hidden="true">&raquo;</span>\n'
        src += '</a>\n'
        src += '</li>\n'
        src += '</ul>\n'
        src += '</div>\n'

        src += '<div class="row justify-content-center">\n'

        src += '<style type="text/css">#blockchain-table td {padding: 0px 5px; font-size: 0.8em; font-family: monospace, monospace; }</style>'

        src += '<div class="table-responsive">\n'
        src += '<table id="blockchain-table" class="table table-bordered table-hover">\n'

        src += '<tr bgcolor=white>\n'
        src += '<td><b>TXID</b></td>\n'
        src += '<td><b>Timestamp</b></td>\n'
        src += '<td><b>From</b></td>\n'
        src += '<td><b>To</b></td>\n'
        src += '<td><b>Amount</b></td>\n'
        src += '<td><b>Hash</b></td>\n'
        src += '<td><b>Fee</b></td>\n'
        src += '<td><b>Reward</b></td>\n'
        src += '<td><b>Operation</b></td>\n'
        src += '<td><b>Openfield</b></td>\n'
        src += '<td><b>Block</b></td>\n'
        src += '</tr>\n'

        src += ''.join(view)

        src += '</table>\n'
        src += '</div>\n'
        src += '</div>\n'

        src += '<br>\n'
        src += '<div class="row justify-content-center">\n'
        src += '<ul class="pagination pagination-sm">\n'
        src += '<li class="page-item">\n'
        src += '<a class="page-link" href="/?page={}">\n'.format(max(0, page_num - 1))
        src += '<span aria-hidden="true">&laquo;</span>\n'
        src += '</a>\n'
        src += '</li>\n'
        src += '<li class="page-item">\n'
        src += '<a class="page-link" href="/?page={}">\n'.format(min(page_max, page_num + 1))
        src += '<span aria-hidden="true">&raquo;</span>\n'
        src += '</a>\n'
        src += '</li>\n'
        src += '</ul>\n'
        src += '</div>\n'

        src += '</div>\n'
        src += '</div>\n'
        src += '</div>\n'
        src += '</div>\n'

        html_src = web_html_template.WEB_ROOT_TEMPLATE % dict(
            title='BitDust blockchain explorer',
            site_url='https://bitdust.io',
            basepath='https://%s/' % _ExplorerHost,
            wikipath='https://bitdust.io/wiki/',
            idserverspath='https://identities.bitdust.io/',
            blockchainpath='https://blockchain.bitdust.io/',
            div_main_class='main blockchain',
            div_main_body=src,
            google_analytics='',
            pre_footer='',
        )
        return strng.to_bin(html_src)


#------------------------------------------------------------------------------


class BlockchainTransactionPage(resource.Resource):

    def __init__(self, tx_id):
        resource.Resource.__init__(self)
        self.tx_id = tx_id

    def render_GET(self, request):
        src = ''
        src += '<div id="ui-blockchain-transaction" class="section bg-light">'
        src += '<div class="container">\n'
        src += '<div class="ui-card">\n'
        src += '<div class="card-body">\n'

        try:
            _t = strng.to_text(base64.b64decode(self.tx_id, altchars='-_'))
        except:
            src += '<p align=center>invalid transaction ID</p>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            html_src = web_html_template.WEB_ROOT_TEMPLATE % dict(
                title='BitDust blockchain explorer',
                site_url='https://bitdust.io',
                basepath='https://%s/' % _ExplorerHost,
                wikipath='https://bitdust.io/wiki/',
                idserverspath='https://identities.bitdust.io/',
                blockchainpath='https://blockchain.bitdust.io/',
                div_main_class='main blockchain-transaction',
                div_main_body=src,
                google_analytics='',
                pre_footer='',
            )
            return strng.to_bin(html_src)

        try:
            conn = sqlite3.connect(bismuth_node.nod().ledger_path, timeout=60.0)
            c = conn.cursor()
            execute(c, 'SELECT * FROM transactions WHERE substr(signature,1,4)=substr(?1,1,4) and signature like ?1;', (_t + '%', ))
            raw = c.fetchone()
            c.close()
            conn.close()
            conn = None
            c = None
        except:
            src += '<p align=center>reading failed</p>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            html_src = web_html_template.WEB_ROOT_TEMPLATE % dict(
                title='BitDust blockchain explorer',
                site_url='https://bitdust.io',
                basepath='https://%s/' % _ExplorerHost,
                wikipath='https://bitdust.io/wiki/',
                idserverspath='https://identities.bitdust.io/',
                blockchainpath='https://blockchain.bitdust.io/',
                div_main_class='main blockchain-transaction',
                div_main_body=src,
                google_analytics='',
                pre_footer='',
            )
            return strng.to_bin(html_src)

        if not raw:
            src += '<p align=center>invalid transaction ID</p>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            src += '</div>\n'
            html_src = web_html_template.WEB_ROOT_TEMPLATE % dict(
                title='BitDust blockchain explorer',
                site_url='https://bitdust.io',
                basepath='https://%s/' % _ExplorerHost,
                wikipath='https://bitdust.io/wiki/',
                idserverspath='https://identities.bitdust.io/',
                blockchainpath='https://blockchain.bitdust.io/',
                div_main_class='main blockchain-transaction',
                div_main_body=src,
                google_analytics='',
                pre_footer='',
            )
            return strng.to_bin(html_src)

        src += '<div>block: <b>{}</b></div><br>\n'.format(raw[0])
        src += '<div>block hash: <b><code>{}</code></b></div><br>\n'.format(raw[7])
        src += '<div>timestamp: <b>{}</b></div><br>\n'.format(time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime(float(raw[1]))))
        src += '<div>sender: <b><code>{}</code></b></div><br>\n'.format(raw[2])
        src += '<div>recipient: <b><code>{}</code></b></div><br>\n'.format(raw[3])
        src += '<div>amount: <b>{}</b></div><br>\n'.format(misc.float2str(raw[4], mask='%10.12f'))
        src += '<div>fee: <b>{}</b></div><br>\n'.format(misc.float2str(raw[8], mask='%10.12f'))
        src += '<div>reward: <b>{}</b></div><br>\n'.format(misc.float2str(raw[9], mask='%10.12f'))
        src += '<div>operation: <b>{}</b></div><br>\n'.format(raw[10])
        src += '<div style="margin: 0 auto; overflow-wrap: break-word; word-wrap: break-word;">openfield: <b><code>{}</code></b></div><br>\n'.format(raw[11])
        src += '<div style="margin: 0 auto; overflow-wrap: break-word; word-wrap: break-word;">signature:\n<b><code>{}</code></b></div><br>\n'.format(self.tx_id)
        src += '</div>\n'
        src += '</div>\n'
        src += '</div>\n'
        src += '</div>\n'

        html_src = web_html_template.WEB_ROOT_TEMPLATE % dict(
            title='BitDust blockchain explorer',
            site_url='https://bitdust.io',
            basepath='https://%s/' % _ExplorerHost,
            wikipath='https://bitdust.io/wiki/',
            idserverspath='https://identities.bitdust.io/',
            blockchainpath='https://blockchain.bitdust.io/',
            div_main_class='main blockchain-transaction',
            div_main_body=src,
            google_analytics='',
            pre_footer='',
        )
        return strng.to_bin(html_src)


#------------------------------------------------------------------------------


class BlockchainRootPage(resource.Resource):

    def getChild(self, path, request):
        if not path:
            return self
        try:
            path = strng.to_text(path)
        except:
            return resource.NoResource('Not found')
        if path:
            return BlockchainTransactionPage(path)
        return resource.NoResource('Not found')


#------------------------------------------------------------------------------


def main():
    bismuth_node.init()
    settings.init()
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)  # @UndefinedVariable
    reactor.callWhenRunning(init)  # @UndefinedVariable
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


#------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
