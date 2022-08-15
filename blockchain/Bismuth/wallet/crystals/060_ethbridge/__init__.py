"""
ETH Bridge Crystal for Tornado wallet
"""

from os import path
from modules.helpers import async_get_with_http_fallback
from modules.basehandlers import CrystalHandler
from modules.helpers import base_path
from hashlib import sha256
from decimal import Decimal, getcontext, ROUND_HALF_EVEN

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/060_ethbridge/themes/default")

MODULES = {}

__version__ = "1.0.4"


# ETH_BRIDGE_ADDRESS = "Bis1SCxtbRiDgEjwu5DZ6tb6P3PnZY2j3CJWg"  # Test
ETH_BRIDGE_ADDRESS = "Bis1UBRiDGEQc9mBywXpwFZX6LF7hN4i8Qy9m"  # Prod

# ETH_ORACLE_ADDRESS = "Bis1WaEthEtHeyEbh8wckQrnZnR88XJK8xDFb"  # Test
ETH_ORACLE_ADDRESS = "Bis1XETHbisxnShtghYQJDbf8o5gsQczW8Gp2"  # Prod

# ETH_SC_ADDRESS = "0x29B3fF6d2E194ac99D4ca4356251829651D08b94"  # Test v6
ETH_SC_ADDRESS = "0xf5cB350b40726B5BcF170d12e162B6193b291B41"  # Mainnet
ETH_wBIS_URL = "https://raw.githubusercontent.com/bismuthfoundation/MEDIA-KIT/master/Logo_v2/wbis500x500.png"
# ETH_EXPLORER = "https://goerli.etherscan.io"  # test
ETH_EXPLORER = "https://etherscan.io"  # mainnet

BIS_FIXED_FEES_FLOAT = 5.0
BIS_FIXED_FEES_INT = 500000000

# From bismuthCore, to avoid one more requirements, at expanse of dup code.
getcontext().rounding = ROUND_HALF_EVEN
# Multiplier to convert floats to int
DECIMAL_1E8 = Decimal(100000000)


def int_to_f8(an_int: int):
    # Helper function to convert an int amount - inner format - to legacy string 0.8f
    return str('{:.8f}'.format(Decimal(an_int) / DECIMAL_1E8))


def f8_to_int(a_str: str):
    # Helper function to convert a legacy string 0.8f to compact int format
    return int(Decimal(a_str) * DECIMAL_1E8)


class EthbridgeHandler(CrystalHandler):

    def initialize(self):
        # This method is not needed if you don't need custom init code,
        # else include it and add your own code after super()...
        super().initialize()
        scripts = ['helpers.js', 'web3.min.js', 'wbis_abi.js', 'bridge.js']
        footer = ""
        # footer += '<script src="https://unpkg.com/default-passive-events"></script>\n'
        for script in scripts:
            footer += f'<script src= "/crystal/ethbridge/static/{script}"></script>\n'
        self.bismuth_vars['extra'] = {"header": '', "footer": footer,
                                      "ethbridge_address": ETH_BRIDGE_ADDRESS,
                                      "ethoracle_address": ETH_ORACLE_ADDRESS,
                                      "eth_sc_address": ETH_SC_ADDRESS,
                                      "eth_wbis_url": ETH_wBIS_URL,
                                      "eth_explorer": ETH_EXPLORER,
                                      "bis_fixed_fees": BIS_FIXED_FEES_FLOAT,
                                      "bis_confs": 15, "eth_confs": 15}

    @staticmethod
    def sha256(txid: str):
        return sha256(txid.encode('utf-8')).hexdigest()

    async def about(self, params=None):
        self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/about.js"></script>\n'
        self.bismuth_vars['extra']["circulating"] = "N/A"
        try:
            res = await async_get_with_http_fallback("https://hypernodes.bismuth.live/api/coinsupply.php")
            # print(res)
            self.bismuth_vars['extra']["circulating"] = res["circulating"]
        except:
            pass
        self.render("about.html", bismuth=self.bismuth_vars)

    async def message_popup(self, params=None):
        title = self.get_argument("title", default=None, strip=False)
        message = self.get_argument("msg", default=None, strip=False)
        message_type = self.get_argument("type", default=None, strip=False)
        self.render("message_pop.html", bismuth=self.bismuth_vars, title=title, message=message, type=message_type)

    async def to_eth2(self, params=None):
        """
        /crystal/ethbridge/to_eth2?eth_address=0x&amount=10&txidhash=0x&auth=0x
        """
        mint = dict()
        mint["eth_address"] = self.get_argument("eth_address", "0x")
        mint["amount"] = self.get_argument("amount", "10")
        mint["txidhash"] = self.get_argument("txidhash", "0x")
        mint["auth"] = self.get_argument("auth", "0x")
        data = {}
        self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/to_eth2.js"></script>\n'
        self.render("to_eth2.html", bismuth=self.bismuth_vars, data=data, mint=mint)

    async def to_eth1(self, params=None):
        """
        """
        data = {}
        # self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/to_eth2.js"></script>\n'
        self.render("to_eth1.html", bismuth=self.bismuth_vars, data=data)

    async def from_eth1(self, params=None):
        """
        """
        data = {}
        # self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/to_eth2.js"></script>\n'
        self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/from_eth1.js"></script>\n'
        self.render("from_eth1.html", bismuth=self.bismuth_vars, data=data)

    async def swaps(self, params=None):
        """
        """
        data = dict()
        data["bis_address"] = self.get_argument("bis_address", self.bismuth_vars["address"])
        # self.bismuth_vars['extra']["footer"] += f'<script src= "/crystal/ethbridge/static/to_eth2.js"></script>\n'
        """bis_data = self.bismuth.command("listopfromto",
                            [self.bismuth_vars["address"], ETH_BRIDGE_ADDRESS, "ethbridge:send", 10, True, 0, 9e10]
                                        )
        """
        command = "addlistopfromtojson"
        # sender, recipient, op, amount,
        #         order descending/ascending, start and end timestamps
        bismuth_params = [data["bis_address"], ETH_BRIDGE_ADDRESS,
                          'ethbridge:send', '0.00000000', True, 0, 9e10]
        bis_data = self.bismuth.command(command, bismuth_params)

        txid_hashes = dict()
        for tx in bis_data:
            try:
                id_hash = self.sha256(tx["signature"][:56])
                amount_after_fees = float(tx["amount"]) - BIS_FIXED_FEES_FLOAT
                fees = BIS_FIXED_FEES_FLOAT
                txid_hashes[id_hash] = {"status": 0, "direction": 1, "txid1": tx["signature"][:56],
                                        "ts1": tx["timestamp"], "block1": tx["block_height"],
                                        "bis_address": tx["address"], "eth_address": tx["openfield"],
                                        "eth_txid": "",
                                        "amount": tx["amount"],
                                        "amount_after_fees": amount_after_fees, "fees": fees,
                                        "mint_signature": "", "ts_signature": 0}
                # Status 0: Bis -> wbis, not signed
            except Exception as e:
                pass

        # print(bis_data)
        data['bismuth_transactions'] = bis_data

        command = "addlistopfromtojson"
        # sender, recipient, op, amount,
        #         order descending/ascending, start and end timestamps
        bismuth_params = [ETH_ORACLE_ADDRESS, data["bis_address"],
                          'ethbridge:burn', '0.00000000', True, 0, 9e10]
        bis_data = self.bismuth.command(command, bismuth_params)
        # TODO: query eth oracle for latest known eth_height
        for tx in bis_data:
            try:
                (id_hash, tx_height, eth_height, eth_address, amount_int) = tx["openfield"].split(":")
                eth_height = int(eth_height)
                tx_height = int(tx_height)
                if eth_height > self.bismuth_vars['extra'].get('eth_height', 0):
                    # also update
                    self.bismuth_vars['extra']['eth_height'] = eth_height
                amount_after_fees = float(int_to_f8(int(amount_int))) - BIS_FIXED_FEES_FLOAT  # o_O
                fees = BIS_FIXED_FEES_FLOAT
                txid_hashes[id_hash] = {"status": 0, "direction": 2, "txid1": "",
                                        "ts1": tx["timestamp"], "block1": tx_height,
                                        "bis_address": tx["recipient"], "eth_address": eth_address,
                                        "eth_txid": id_hash,
                                        "amount": int_to_f8(amount_int),
                                        "amount_after_fees": amount_after_fees, "fees": fees,
                                        "mint_signature": "", "ts_signature": 0}
                print("BURN ", txid_hashes[id_hash])
                # Status 0: Bis -> wbis, not signed
            except Exception as e:
                print("burn ex", e)
                pass
        # print("burn", bis_data)

        data['eth_transactions'] = bis_data

        bismuth_params = [ETH_BRIDGE_ADDRESS, data["bis_address"], 'ethbridge:signature', '0.00000000', True, 0, 9e10]
        bis_data = self.bismuth.command(command, bismuth_params)
        for tx in bis_data:
            try:
                (id_hash, mint_signature, amount_int) = tx["openfield"].split(":")
                if id_hash in txid_hashes:
                    txid_hashes[id_hash]["status"] = 1
                    txid_hashes[id_hash]["mint_signature"] = mint_signature
                    txid_hashes[id_hash]["ts_signature"] = tx["timestamp"]
                    txid_hashes[id_hash]["amount_after_fees"] = int_to_f8(amount_int)
            except Exception as e:
                pass
        # Once wBIS Minted
        bismuth_params = [ETH_ORACLE_ADDRESS, data["bis_address"], 'ethbridge:proxymint', '0.00000000', True, 0, 9e10]
        bis_data = self.bismuth.command(command, bismuth_params)
        # print("proxymint", bis_data)
        for tx in bis_data:
            try:
                (id_hash, eth_txid, eth_address, amount_int) = tx["openfield"].split(":")
                if id_hash in txid_hashes:
                    txid_hashes[id_hash]["status"] = 2
                    # Assert: txid_hashes[id_hash]["eth_address"] = eth_address
                    # assert recipient is right one
                    txid_hashes[id_hash]["eth_txid"] = eth_txid
            except Exception as e:
                pass
        # Once BIS delivered
        bismuth_params = [ETH_BRIDGE_ADDRESS, data["bis_address"], 'ethbridge:deliver', '0.00000000', True, 0, 9e10]
        bis_data = self.bismuth.command(command, bismuth_params)
        # print("proxymint", bis_data)
        for tx in bis_data:
            try:
                eth_txid = tx["openfield"]
                id_hash = eth_txid
                if id_hash in txid_hashes:
                    txid_hashes[id_hash]["status"] = 2
                    # Assert: txid_hashes[id_hash]["eth_address"] = eth_address
                    # assert recipient is right one
                    txid_hashes[id_hash]["txid1"] = tx["signature"][:56]
                    txid_hashes[id_hash]["ts_signature"] = tx["timestamp"]
            except Exception as e:
                pass
        # print(bis_data)
        data['swaps'] = bis_data
        data["hashes"] = txid_hashes
        self.render("swaps.html", bismuth=self.bismuth_vars, data=data)

    async def get(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        await getattr(self, command)(params)

    async def post(self, command=""):
        command, *params = command.split("/")
        if command:
            await getattr(self, command)(params)

    def get_template_path(self):
        """Override to customize template path for each handler."""
        return DEFAULT_THEME_PATH

    def static(self):
        """Defining this method will automagically create a static handler pointing to local /static crystal dir"""
        pass
