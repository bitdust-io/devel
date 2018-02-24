import time

from twisted.web import server, resource
from twisted.internet import reactor

import json_coin
import transactions
import util
import traceback
import json

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
#form_block {background-color: %(form_block_bg)s; border: 1px solid %(form_block_border)s;}
#form_block form {margin: 0px;}
#form_transaction {background-color: %(form_transaction_bg)s; border: 1px solid %(form_transaction_border)s;}
#form_transaction form {margin: 0px;}
#form_token {background-color: %(form_token_bg)s; border: 1px solid %(form_token_border)s;}
#form_token_transfer {background-color: %(form_token_transfer_bg)s; border: 1px solid %(form_token_transfer_border)s;}
#form_token_delete {background-color: %(form_token_transfer_bg)s; border: 1px solid %(form_token_transfer_border)s;}
.transaction {background-color: %(transaction_bg)s; border: 1px solid %(transaction_border)s;}
.tr_header {}
.tr_body {}
.tr_inputs {}
.tr_outputs {}
.tr_authorizations {}
.tr_input {background-color: %(tr_input_bg)s; border: 1px solid %(tr_input_border)s;}
.tr_output {background-color: %(tr_output_bg)s; border: 1px solid %(tr_output_border)s;}
.tr_authorization {background-color: %(tr_authorization_bg)s; border: 1px solid %(tr_authorization_border)s;}
.token {background-color: %(token_bg)s; border: 1px solid %(token_border)s;}
.to_payload {float: left; overflow: auto; margin: 2px;}
.to_record {background-color: %(to_record_bg)s; border: 1px solid %(to_record_border)s;}
.field {margin: 0 auto; text-align: left; float: left; padding: 0px 10px; display:inline-block;}
.field-right {margin: 0 auto; text-align: left; float: right; padding: 0px 10px; display:inline-block;}
.field code {font-size: 12px;}
.field input {line-height: 20px; padding:0px 5px; margin: 0px; border: 1px solid #888; border-radius: 3px;}
.field input[type=submit] {line-height: 20px; padding:0px 5px; margin: 0px; border: 1px solid #888; border-radius: 3px;}
.f_json {background-color: %(f_json_bg)s; border: 1px solid %(f_json_border)s; border-radius: 3px;}
""" % css_dict

def colors():
    return dict(
        form_block_bg='#E6E6FA',
        form_block_border='#000080',
        form_transaction_bg='#E6E6FA',
        form_transaction_border='#000080',
        form_token_bg='#E6E6FA',
        form_token_border='#000080',
        form_token_transfer_bg='#E6E6FA',
        form_token_transfer_border='#000080',
        form_token_delete_bg='#E6E6FA',
        form_token_delete_border='#000080',
        transaction_bg='#f8f8f8',
        transaction_border='#d0d0d0',
        tr_input_bg='#e0e0ff',
        tr_input_border='#c0c0df',
        tr_output_bg='#e0ffe0',
        tr_output_border='#c0dfc0',
        tr_authorization_bg='#ffe0e0',
        tr_authorization_border='#dfc0c0',
        f_json_bg='#FAFAD2',
        f_json_border='#dfc0c0',
        token_bg='#fff099',
        token_border='#d0d0d0',
        to_record_bg='#e0ffe0',
        to_record_border='#c0dfc0',
        to_payload_bg='#e0e0ff',
        to_payload_border='#c0dfc0',
    )

#------------------------------------------------------------------------------

class MainPage(resource.Resource):
    isLeaf = True
    peer = None

    def __init__(self, peer, wallet, *args, **kwargs):
        resource.Resource.__init__(self)
        self.peer = peer
        self.wallet = wallet

    def _solve_block(self, json_data=None):
        new_block = self.peer.blockchain.make_block(
            self.wallet.get_address(),
            json_data=json_data,
            with_inputs=False,
            # with_outputs=False,
        )
        if not new_block:
            return None
        if not new_block.do_some_work(self.peer.blockchain.algorithm,
                                      iterations=10000000):
            return None
        self.peer.send_block(new_block)
        return new_block

    def render_POST(self, request):
        command = request.args.get('command', ['', ])[0]
        #--- solve block ---
        if command == 'solve block':
            json_data = request.args.get('json', ['{}', ])[0]
            try:
                json_data = json.loads(json_data or '{}')
                new_block = self._solve_block(json_data)
                if new_block:
                    result = self.peer.blockchain.dump_block(new_block)
                    code = 'OK'
                else:
                    result = 'Block was not solved'
                    code = 'OK'
            except:
                result = traceback.format_exc()
                code = 'ERROR'

        #--- create output ---
        elif command == 'create output':
            destination = request.args.get('destination', ['', ])[0]
            amount = request.args.get('amount', ['0', ])[0]
            json_data = request.args.get('json', ['{}', ])[0]
            fee = request.args.get('fee', ['1', ])[0]
            try:
                amount = int(amount or 0)
                fee = int(fee or 1)
                json_data = json.loads(json_data or '{}')
                new_transaction = self.wallet.make_simple_transaction(
                    amount,
                    util.string2bytes(destination),
                    fee=fee,
                    json_data=json_data,
                )
                if new_transaction:
                    self.peer.send_transaction(new_transaction.to_bytes())
                    result = str(new_transaction)
                    code = 'OK'
                else:
                    result = 'Invalid transaction'
                    code = 'FAILED'
            except:
                result = traceback.format_exc()
                code = 'ERROR'

        #--- create token ---
        elif command == 'create token':
            token_id = request.args.get('token_id', ['', ])[0]
            amount = request.args.get('amount', ['0', ])[0]
            json_data = request.args.get('json', ['{}', ])[0]
            fee = request.args.get('fee', ['1', ])[0]
            try:
                amount = int(amount or 0)
                fee = int(fee or 1)
                json_data = json.loads(json_data or '{}')
                new_transaction = self.wallet.token_create(
                    token_id,
                    amount,
                    fee=fee,
                    payload=json_data,
                )
                if new_transaction:
                    self.peer.send_transaction(new_transaction.to_bytes())
                    result = str(new_transaction)
                    code = 'OK'
                else:
                    result = 'Invalid transaction'
                    code = 'FAILED'
            except:
                result = traceback.format_exc()
                code = 'ERROR'

        #--- transfer token ---
        elif command == 'transfer token':
            token_id = request.args.get('token_id', ['', ])[0]
            amount = request.args.get('amount', ['0', ])[0]
            destination = request.args.get('destination', ['', ])[0]
            fee = request.args.get('fee', ['1', ])[0]
            json_data = request.args.get('json', ['{}', ])[0]
            json_history = bool(request.args.get('json_history', ['', ])[0])
            try:
                amount = int(amount or 0)
                fee = int(fee or 1)
                json_data = json.loads(json_data or '{}')
                new_transaction = self.wallet.token_transfer(
                    token_id,
                    util.string2bytes(destination),
                    new_value=amount,
                    fee=fee,
                    payload=json_data,
                    payload_history=json_history,
                )
                if new_transaction:
                    self.peer.send_transaction(new_transaction.to_bytes())
                    result = str(new_transaction)
                    code = 'OK'
                else:
                    result = 'Invalid transaction'
                    code = 'FAILED'
            except:
                result = traceback.format_exc()
                code = 'ERROR'

        #--- delete token ---
        elif command == 'delete token':
            token_id = request.args.get('token_id', ['', ])[0]
            destination = request.args.get('destination', ['', ])[0]
            fee = request.args.get('fee', ['1', ])[0]
            try:
                fee = int(fee or 1)
                new_transaction = self.wallet.token_delete(
                    token_id,
                    address=destination,
                    fee=fee,
                )
                if new_transaction:
                    self.peer.send_transaction(new_transaction.to_bytes())
                    result = str(new_transaction)
                    code = 'OK'
                else:
                    result = 'Invalid transaction'
                    code = 'FAILED'
            except:
                result = traceback.format_exc()
                code = 'ERROR'

        else:
            result = 'Wrong command'
            code = 'ERROR'

        return '''
<head>
<title>PyBC Wallet on %(hostname)s:%(hostinfo)s</title>
<style>%(css)s</style>
</head>
<body>
<div id="content">
<pre>%(result)s</pre>
result: %(code)s
<form method="get" action="">
<input type=submit value="back">
</form>
</div>
</body>
</html>''' % dict(
            hostname=self.peer.external_address,
            hostinfo=self.peer.port,
            css='',
            result=result,
            code=code,
        )

    def render_GET(self, request):
        src = '''
<head>
<title>PyBC Wallet on %(hostname)s:%(hostinfo)s</title>
<style>%(css)s</style>
</head>
<body>''' % dict(
            hostname=self.peer.external_address,
            hostinfo=self.peer.port,
            css=css_styles(colors()),
        )
        src += '<div id="content">\n'
        src += '<h1>PyBC Wallet on %(hostname)s:%(hostinfo)s</h1>\n' % dict(
            hostname=self.peer.external_address,
            hostinfo=self.peer.port,
        )
        src += '<h2>address: <code>{}</code></h2>\n'.format(
            util.bytes2string(self.wallet.get_address()))
        src += '<h2>current balance: {}</h2>\n'.format(self.wallet.get_balance())
        src += 'network name: {}<br>\n'.format(self.peer.network)
        src += 'software version: {}<br>\n'.format(self.peer.version)
        src += 'number of blocks: {}<br>\n'.format(len(self.peer.blockchain.blockstore))
        src += 'local disk usage: {} bytes<br><br>\n'.format(self.peer.blockchain.get_disk_usage())
        #--- form_block
        src += '<div id="form_block" class="panel-big">\n'
        src += '<form method="post" action="">\n'
        src += '<div class=field>json:<input size=60 type=text name=json placeholder="{}"/></div>\n'
        src += '<div class="field-right"><input type=submit name="command" value="solve block" /></div>\n'
        src += '</form>\n'
        src += '</div>\n'
        #--- form_transaction
        src += '<div id="form_transaction" class="panel-big">\n'
        src += '<form method="post" action="">\n'
        src += '<div class=field>destination:<input size=42 type=text name=destination placeholder="PyBC address"/></div>\n'
        src += '<div class=field>amount:<input size=4 type=text name=amount placeholder="coins"/></div>\n'
        src += '<div class=field>fee:<input size=1 type=text name=fee placeholder="1"/></div>\n'
        src += '<div class=field>json:<input size=40 type=text name=json placeholder="{}"/></div>\n'
        src += '<div class="field-right"><input type=submit name="command" value="create output" /></div>\n'
        src += '</form>\n'
        src += '</div>\n'
        #--- form_token
        src += '<div id="form_token" class="panel-big">\n'
        src += '<form method="post" action="">\n'
        src += '<div class=field>token:<input size=16 type=text name=token_id placeholder="token ID"/></div>\n'
        src += '<div class=field>value:<input size=4 type=text name=amount placeholder="coins"/></div>\n'
        src += '<div class=field>fee:<input size=1 type=text name=fee placeholder="1"/></div>\n'
        src += '<div class=field>json payload:<input size=40 type=text name=json placeholder="{}"/></div>\n'
        src += '<div class="field-right"><input type=submit name="command" value="create token" /></div>\n'
        src += '</form>\n'
        src += '</div>\n'
        #--- form_token_transfer
        src += '<div id="form_token_transfer" class="panel-big">\n'
        src += '<form method="post" action="">\n'
        src += '<div class=field>token:<input size=16 type=text name=token_id placeholder="token ID"/></div>\n'
        src += '<div class=field>destination:<input size=42 type=text name=destination placeholder="PyBC address"/></div>\n'
        src += '<div class=field>new value:<input size=4 type=text name=amount placeholder="coins"/></div>\n'
        src += '<div class=field>fee:<input size=1 type=text name=fee placeholder="1"/></div>\n'
        src += '<div class=field>json:<input size=30 type=text name=json placeholder="{}"/></div>\n'
        src += '<div class=field>history:<input size=1 type=checkbox name=json_history checked /></div>\n'
        src += '<div class="field-right"><input type=submit name="command" value="transfer token" /></div>\n'
        src += '</form>\n'
        src += '</div>\n'
        #--- form_token_delete
        src += '<div id="form_token_delete" class="panel-big">\n'
        src += '<form method="post" action="">\n'
        src += '<div class=field>token:<input size=16 type=text name=token_id placeholder="token ID"/></div>\n'
        src += '<div class=field>destination:<input size=42 type=text name=destination placeholder="PyBC address"/></div>\n'
        src += '<div class=field>fee:<input size=1 type=text name=fee placeholder="1"/></div>\n'
        src += '<div class="field-right"><input type=submit name="command" value="delete token" /></div>\n'
        src += '</form>\n'
        src += '</div>\n'
        src += '<h1>tokens:</h1>\n'
        for token_profile in self.wallet.tokens_list():
            src += '<div class="token panel-big">\n'
            src += '<div class="to_header panel-small">\n'
            src += '<b><code>{}</code></b>\n'.format(token_profile.owner().token_id)
            if token_profile.owner().address is None:
                src += '<font color=red>disbanded</font>\n'
            elif token_profile.owner().address != self.wallet.get_address():
                src += '<font color=red>belongs to <b><code>{}</code></b></font>\n'.format(
                    util.bytes2string(token_profile.owner().address, limit=8))
            elif token_profile.creator().address != self.wallet.get_address():
                src += '<font color=gray>created by <b><code>{}</code></b></font>\n'.format(
                    util.bytes2string(token_profile.creator().address, limit=8))
            src += '</div>\n'  # to_header
            src += '<div class="to_body panel-small">\n'
            for token_record in token_profile.records:
                src += '<div class="to_record panel-small">\n'
                src += '<div class="field">{} coins</div>\n'.format(token_record.value())
                src += '<div class="field">from <b><code>{}</code></b></div>\n'.format(
                    util.bytes2string(token_record.prev_address, limit=8) or '<font color=green>$$$</font>')
                src += '<div class="field">to <b><code>{}</code></b></div>\n'.format(
                    util.bytes2string(token_record.address, limit=8) or '<font color=green>$$$</font>')
                for payload in token_record.output_payloads:
                    src += '<div class="to_payload">\n'
                    src += '<div class="field f_json"><code>{}</code></div>\n'.format(payload)
                    src += '</div>\n'  # to_payload
                src += '</div>\n'  # to_record
            src += '</div>\n'  # to_body
            src += '</div><br>\n'  # token
        src += '<h1>related transactions:</h1>\n'
        for tr in self.peer.blockchain.iterate_transactions_by_address(self.wallet.get_address()):
            src += '<div class="transaction panel-big">\n'
            src += '<div class="tr_header panel-small">\n'
            src += '<b>transaction</b> from <i>{}</i>\n'.format(time.ctime(tr.timestamp))
            src += 'hash: <b><code>{}</code></b>,\n'.format(
                util.bytes2string(tr.transaction_hash(), limit=8))
            src += 'block hash: <b><code>{}</code></b>,\n'.format(
                util.bytes2string(tr.block_hash, limit=8))
            src += 'with {} inputs, {} outputs and {} authorizations'.format(
                len(tr.inputs), len(tr.outputs), len(tr.authorizations))
            src += '</div>\n'  # tr_header
            src += '<div class="tr_body panel-small">\n'
            src += '<div class="tr_inputs panel-medium">\n'
            if not tr.inputs:
                src += '<div class="tr_input panel-small">\n'
                src += '<div class="field">no inputs</div>\n'
                src += '</div>\n'  # tr_input
            else:
                for inpt in tr.inputs:
                    src += '<div class="tr_input panel-small">\n'
                    src += '<div class="field f_amount">{}</div>\n'.format(inpt[2])
                    src += '<div class="field f_destination"><b><code>{}</code></b></div>\n'.format(
                        util.bytes2string(inpt[3], limit=8))
                    src += '<div class="field f_index">#{}</div>\n'.format(inpt[1])
                    src += '<div class="field f_hash"><code>{}</code></div>\n'.format(
                        util.bytes2string(inpt[0], limit=8))
                    if inpt[4] is not None:
                        src += '<div class="field f_json"><code>{}</code></div>\n'.format(inpt[4])
                    src += '</div>\n'  # tr_input
            src += '</div>\n'  # tr_inputs
            src += '<div class="tr_outputs panel-medium">\n'
            if not tr.outputs:
                src += '<div class="tr_output panel-small">\n'
                src += '<div class="field">no outputs</div>\n'
                src += '</div>\n'  # tr_output
            else:
                for outpt in tr.outputs:
                    src += '<div class="tr_output panel-small">\n'
                    src += '<div class="field f_amount">{}</div>\n'.format(outpt[0])
                    src += '<div class="field f_destination"></b><code>{}</code></b></div>\n'.format(
                        util.bytes2string(outpt[1], limit=8))
                    if outpt[2] is not None:
                        src += '<div class="field f_json"><code>{}</code></div>\n'.format(outpt[2])
                    src += '</div>\n'  # tr_input
            src += '</div>\n'  # tr_outputs
            src += '<div class="tr_authorizations panel-medium">\n'
            if not tr.authorizations:
                src += '<div class="tr_authorization panel-small">\n'
                src += '<div class="field">no authorizations</div>\n'
                src += '</div>\n'  # tr_authorization
            else:
                for author in tr.authorizations:
                    src += '<div class="tr_authorization panel-small">\n'
                    src += '<div class="field f_pub_key"><code>{}</code></div>\n'.format(
                        util.bytes2string(author[0], limit=10))
                    src += '<div class="field f_signature"><code>{}</code></div>\n'.format(
                        util.bytes2string(author[1], limit=10))
                    if author[2] is not None:
                        src += '<div class="field f_json"><code><code>{}</code></code></div>\n'.format(author[2])
                    src += '</div>\n'  # tr_authorization
            src += '</div>\n'  # tr_authorizations
            src += '</div>\n'  # tr_body
            src += '</div>\n'  # transaction
        src += '</div>\n'  # content
        src += '</body>\n'
        src += '</html>'
        return src


def start(port, peer_instance, wallet_instance):
    site = server.Site(MainPage(peer_instance, wallet_instance))
    return reactor.listenTCP(port, site)
