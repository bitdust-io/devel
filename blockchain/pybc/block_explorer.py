from __future__ import absolute_import
import time

from twisted.web import server, resource
from twisted.internet import reactor  # @UnresolvedImport
from twisted.internet import protocol

from . import json_coin
from . import transactions
from . import util

#------------------------------------------------------------------------------

_BlockIndexByTimestamp = dict()

#------------------------------------------------------------------------------

def build_index(blockchain_instance):
    global _BlockIndexByTimestamp
    _BlockIndexByTimestamp.clear()
    for key, block in blockchain_instance.blockstore.items():
        if block.timestamp not in _BlockIndexByTimestamp:
            _BlockIndexByTimestamp[block.timestamp] = []
        _BlockIndexByTimestamp[block.timestamp].append(key)

#------------------------------------------------------------------------------

def css_styles(css_dict):
    return """
body {margin: 0 auto; padding: 0;}
.panel-big {display: block; padding: 5px; margin-bottom: 5px; border-radius: 10px; overflow: auto;}
.panel-medium {display: block; padding: 2px; margin-bottom: 2px; border-radius: 5px; overflow: auto;}
.panel-small {display: block; padding: 1px; margin-bottom: 1px; border-radius: 3px; overflow: auto;}
#content {margin: 0 auto; padding: 0; text-align: justify; line-height: 16px;
    width: 90%%; font-size: 14px; text-decoration: none;
    font-family: "Century Gothic", Futura, Arial, sans-serif;}
.block {background-color: %(block_background)s;border: 1px solid %(block_border)s;}
.b_header {line-height: 14px;}
.b_body {}
.transaction {background-color: %(transaction_background)s; border: 1px solid %(transaction_border)s;}
.t_header {}
.t_body {}
.t_inputs {position: relative;}
.t_outputs {position: relative;}
.t_authorizations {display: block; margin-top: 3px;}
.t_input {background-color: %(input_background)s; border: 1px solid %(input_border)s;}
.t_output {background-color: %(output_background)s; border: 1px solid %(output_border)s;}
.t_authorization {background-color: %(authorization_background)s; border: 1px solid %(authorization_border)s;}
.field {margin: 0 auto; text-align: left; float: left; padding: 0px 10px; display:inline-block;}
.field-right {margin: 0 auto; text-align: left; float: right; padding: 0px 10px; display:inline-block;}
.field code {font-size: 12px;}
.f_json {background-color: %(f_json_bg)s; border: 1px solid %(f_json_border)s; border-radius: 3px;}
""" % css_dict

#------------------------------------------------------------------------------

class MainPage(resource.Resource):
    isLeaf = True
    peer = None

    def __init__(self, peer, *args, **kwargs):
        resource.Resource.__init__(self)
        self.peer = peer

    def render_GET(self, request):
        global _BlockIndexByTimestamp
        src = '''
<head>
<title>PyBC Node on %(hostname)s:%(hostinfo)s</title>
<style>%(css)s</style>
</head>
<body>''' % dict(
            hostname=self.peer.external_address,
            hostinfo=self.peer.port,
            css=css_styles(dict(
                block_background='#f0f0f0',
                block_border='c0c0c0',
                transaction_background='#fdfdfd',
                transaction_border='#d0d0d0',
                input_background='#e0e0ff',
                input_border='#c0c0df',
                output_background='#e0ffe0',
                output_border='#c0dfc0',
                authorization_background='#ffe0e0',
                authorization_border='#dfc0c0',
                f_json_bg='#FAFAD2',
                f_json_border='#dfc0c0',
            )),
        )
        src += '<div id="content">\n'
        src += '<h1>PyBC Node on {}:{}</h1>\n'.format(self.peer.external_address, self.peer.port)
        src += 'network name: {}<br>\n'.format(self.peer.network)
        src += 'software version: {}<br>\n'.format(self.peer.version)
        src += 'number of blocks: {}<br>\n'.format(len(self.peer.blockchain.blockstore))
        src += 'local disk usage: {}<br>\n'.format(self.peer.blockchain.get_disk_usage())
        src += '<h1>blocks:</h1>\n'
        for block in self.peer.blockchain.longest_chain():
            src += '<div class="block panel-big">\n'
            src += '<div class="b_header panel-small">\n'
            src += '<b><code>{}</code></b> from <i>{}</i>,\n'.format(
                util.bytes2string(block.block_hash(), limit=8), time.ctime(block.timestamp))
            src += 'previous hash: <b><code>{}</code></b>,\n'.format(
                util.bytes2string(block.previous_hash, limit=8))
            src += 'state hash: <code>{}</code>,\n'.format(
                util.bytes2string(block.state_hash, limit=8))
            src += 'body hash: <code>{}</code>,\n'.format(
                util.bytes2string(block.body_hash, limit=8))
            src += 'nonce: {}, height: {},  payload size: {} bytes \n'.format(
                block.nonce, block.height, len(block.payload))
            src += '</div>\n'  # b_header
            src += '<div class="b_body panel-small">\n'
            if not block.has_body:
                src += 'EMPTY BODY\n'
            else:
                for transaction_bytes in transactions.unpack_transactions(block.payload):
                    tr = json_coin.JsonTransaction.from_bytes(transaction_bytes)
                    src += '<div class="transaction panel-medium">\n'
                    src += '<div class="t_header panel-small">\n'
                    src += '<b>transaction</b> from <i>{}</i>, hash: <b><code>{}</code></b>\n'.format(
                        time.ctime(tr.timestamp), util.bytes2string(tr.transaction_hash(), limit=8))
                    src += '</div>\n'  # t_header
                    src += '<div class="t_body panel-small">\n'
                    src += '<div class="t_inputs panel-medium">\n'
                    if not tr.inputs:
                        src += '<div class="t_input panel-small">\n'
                        src += '<div class="field">no inputs</div>\n'
                        src += '</div>\n'  # t_input
                    else:
                        for inpt in tr.inputs:
                            src += '<div class="t_input panel-small">\n'
                            src += '<div class="field f_amount">{}</div>\n'.format(inpt[2])
                            src += '<div class="field f_destination"><b><code>{}</code></b></div>\n'.format(
                                util.bytes2string(inpt[3], limit=8))
                            src += '<div class="field f_index">#{}</div>\n'.format(inpt[1])
                            src += '<div class="field f_hash"><code>{}</code></div>\n'.format(
                                util.bytes2string(inpt[0], limit=8))
                            if inpt[4] is not None:
                                src += '<div class="field f_json"><code>{}</code></div>\n'.format(inpt[4])
                            src += '</div>\n'  # t_input
                    src += '</div>\n'  # t_inputs
                    src += '<div class="t_outputs panel-medium">\n'
                    if not tr.outputs:
                        src += '<div class="t_output panel-small">\n'
                        src += '<div class="field">no outputs</div>\n'
                        src += '</div>\n'  # t_output
                    else:
                        for outpt in tr.outputs:
                            src += '<div class="t_output panel-small">\n'
                            src += '<div class="field f_amount">{}</div>\n'.format(outpt[0])
                            src += '<div class="field f_destination"><b><code>{}</code></b></div>\n'.format(
                                util.bytes2string(outpt[1], limit=8))
                            if outpt[2] is not None:
                                src += '<div class="field f_json"><code>{}</code></div>\n'.format(outpt[2])
                            src += '</div>\n'  # t_input
                    src += '</div>\n'  # t_outputs
                    src += '<div class="t_authorizations panel-medium">\n'
                    if not tr.authorizations:
                        src += '<div class="t_authorization panel-small">\n'
                        src += '<div class="field">no authorizations</div>\n'
                        src += '</div>\n'  # t_authorization
                    else:
                        for author in tr.authorizations:
                            src += '<div class="t_authorization panel-small">\n'
                            src += '<div class="field f_pub_key"><code>{}</code></div>\n'.format(
                                util.bytes2string(author[0], limit=10))
                            src += '<div class="field f_signature"><code>{}</code></div>\n'.format(
                                util.bytes2string(author[1], limit=10))
                            if author[2] is not None:
                                src += '<div class="field f_json"><code>{}</code></div>\n'.format(author[2])
                            src += '</div>\n'  # t_authorization
                    src += '</div>\n'  # t_authorizations
                    src += '</div>\n'  # t_body
                    src += '</div>\n'  # transaction
            src += '</div>\n'  # b_body
            src += '</div>\n'  # block
        src += '</div>\n'  # content
        src += '</body>\n'
        src += '</html>'
        return src


def start(port, peer_instance):
    site = server.Site(MainPage(peer_instance))
    return reactor.listenTCP(port, site)
