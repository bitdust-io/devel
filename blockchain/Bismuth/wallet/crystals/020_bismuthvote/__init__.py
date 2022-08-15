"""
Bismuth Voting Crystal for Tornado wallet
"""

# import json
from os import path
# from os import listdir
from time import time

from modules.basehandlers import CrystalHandler
from modules.helpers import base_path, get_private_dir, async_get_with_http_fallback
# from tornado.template import Template
from bismuthvoting.bip39 import BIP39
from bismuthvoting.derivablekey import DerivableKey
from secrets import token_bytes
from base64 import b64encode, b64decode

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/020_bismuthvote/themes/default")

MODULES = {}

__version__ = "0.3"


MASTER_KEY = ""
KEYFILE = ""

BGVP_MOTIONS = {}


def status_to_gui_status(status: str) -> str:
    """Converts a motion status into material icon status"""
    if status == "Planned":
        return "assignment"
    elif status == "Voting...":
        return "assignment_late"
    elif status == "Reading...":
        return "assignment_ind"
    return "assignment_turned_in"


async def fill_motions():
    global BGVP_MOTIONS
    BGVP_MOTIONS = await async_get_with_http_fallback("https://hypernodes.bismuth.live/api/voting/motions.json")
    print(BGVP_MOTIONS)
    for id, motion in BGVP_MOTIONS.items():
        BGVP_MOTIONS[id]["Material_status"] = status_to_gui_status(motion["Status"])


def fill_click(motion, address, voting_key=None):
    """Quick and dirty trick to avoid escape hell and too specific js code in the framework.
    Python generated js code
    Not happy with it, but does the job."""
    if not MASTER_KEY:
        return
    # Get the key ready if not provided
    if voting_key is None:
        # print("Derivation path", "{}/{}".format(address, motion["Motion_id"]))
        voting_key = DerivableKey.get_from_path(MASTER_KEY, "{}/{}".format(address, motion["Motion_id"]))
    clicks = []
    for option in motion["Options"]:
        encrypted = DerivableKey.encrypt_vote(voting_key.to_aes_key(), option['option_value'])
        # Precalc the messages, so we can use the js framework to send only.
        openfield = "{}:{}".format(motion["Motion_number"], b64encode(encrypted).decode("utf-8"))
        js = "if(document.getElementById('amount').value<=0){{alert('Enter vote weight!');return false;}};send('{}', document.getElementById('amount').value, 'bgvp:vote', '{}')" \
            .format(motion["Motion_address"], openfield)
        text1 = "BGV-{}/{}".format(motion["Motion_number"], option['option_value'])
        text2 = option['option_title']
        control = DerivableKey.decrypt_vote(voting_key.to_aes_key(), encrypted)
        if control != option['option_value']:
            raise RuntimeWarning("Assertion error checking vote")
        clicks.append({'js': js, 'text1': text1, 'text2': text2, "control": control})
    motion['Clicks'] = clicks
    openfield = "{}:{}".format(motion["Motion_number"], b64encode(voting_key.to_aes_key()).decode("utf-8"))
    js = "send('{}', 0, 'bgvp:reveal', '{}')".format(motion["Motion_address"], openfield)
    motion['Reveal_click'] = js
    return motion


def decode_tx(motion: dict, transaction: dict, voting_key) -> dict:
    """Add decoded key to the transaction, with ok an error info as well."""
    decoded = "Error"
    transaction["ok"] = False
    transaction["error"] = "N/A"
    try:
        if transaction['operation'] == "bgvp:vote":
            # decode the vote
            num, b64 = transaction["openfield"].split(":")
            encrypted = b64decode(b64)
            decoded = "{}:{}".format(num, DerivableKey.decrypt_vote(voting_key.to_aes_key(), encrypted))
            # TODO: make sure vote is one of the motion option
            transaction["ok"] = True
        elif transaction['operation'] == "bgvp:change":
            # decode the vote chyange
            num, b64 = transaction["openfield"].split(":")
            encrypted = b64decode(b64)
            decoded = "{}:{}".format(num, DerivableKey.decrypt_vote(voting_key.to_aes_key(), encrypted))
            # TODO: make sure vote is one of the motion option
            transaction["ok"] = True
        elif transaction['operation'] == "bgvp:reveal":
            num, b64 = transaction["openfield"].split(":")
            decoded = "{}:{}".format(num, b64decode(b64).hex())
            # TODO: make sure it's the current aes key
            transaction["ok"] = True
    except Exception as e:
        decoded = "Error"
        transaction["ok"] = False
        transaction["error"] = str(e)
    transaction["decoded"] = decoded
    return transaction


class BismuthvoteHandler(CrystalHandler):
    async def about(self, params=None):

        voting = {
            "masterkey": MASTER_KEY,
            "masterkey_file": KEYFILE,
            "key_check": BIP39.check(MASTER_KEY),
        }
        await fill_motions()
        voting["bgvp_motions"] = BGVP_MOTIONS
        self.render(
            "about.html", bismuth=self.bismuth_vars, version=__version__, voting=voting
        )

    async def motion(self, params=None):
        # message if no key is set.
        if not MASTER_KEY:
            self.message("Master Key needed", "You need to define your master key first.", type="warning")
            return
        await fill_motions()
        motion_id = str(int(params[0]))  # avoid invalid inputs
        motion = BGVP_MOTIONS[motion_id]
        my_address = self.bismuth_vars['address']
        voting_key = DerivableKey.get_from_path(MASTER_KEY, "{}/{}".format(my_address, motion["Motion_id"]))
        motion = fill_click(motion, my_address, voting_key)
        motion["aes_key_hex"] = voting_key.to_aes_key().hex()
        stats = await async_get_with_http_fallback("https://hypernodes.bismuth.live/api/voting/{}.json".format(motion_id))
        # Optimized command from wallet server.
        command = "addlistopfromjson"
        bismuth_params = [self.bismuth_vars['address'], 'bgvp:vote']
        votes = self.bismuth.command(command, bismuth_params)
        bismuth_params = [self.bismuth_vars['address'], 'bgvp:change']
        changes = self.bismuth.command(command, bismuth_params)
        # TODO: validate changes (can be done in decode_tx)
        bismuth_params = [self.bismuth_vars['address'], 'bgvp:reveal']
        reveals = self.bismuth.command(command, bismuth_params)
        # TODO: validate reveals (can be done in decode_tx)
        transactions = votes + changes + reveals
        transactions = [decode_tx(motion, transaction, voting_key) for transaction in transactions if transaction['recipient'] == motion['Motion_address'] and transaction['openfield'].split(':', 1)[0] == str(motion['Motion_number'])]
        self.render("motion.html", bismuth=self.bismuth_vars, version=__version__, motion=motion, transactions=transactions, stats=stats, now=time())

    async def set_key(self, params=None):
        masterkey = self.get_argument("masterkey", None)
        # print("key", masterkey)
        if not masterkey:
            # Generate a new one
            entropy = token_bytes(16)
            print(entropy)
            bip39 = BIP39(entropy)
            masterkey = bip39.to_mnemonic()
        with open(KEYFILE, "w") as fp:
            fp.write(masterkey)
        global MASTER_KEY
        MASTER_KEY = masterkey
        self.redirect("/crystal/bismuthvote/")

    async def get(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        await getattr(self, command)(params)

    def get_template_path(self):
        """Override to customize template path for each handler.
        """
        return DEFAULT_THEME_PATH


def action_init(params=None):
    """Load and compiles module templates"""
    """
    modules_dir = path.join(DEFAULT_THEME_PATH, "modules")
    for module in listdir(modules_dir):
        module_name = module.split(".")[0]
        file_name = path.join(modules_dir, module)
        with open(file_name, "rb") as f:
            MODULES[module_name] = Template(f.read().decode("utf-8"))            
    """
    global MASTER_KEY
    global KEYFILE
    KEYFILE = path.join(get_private_dir(), "votingkey.json")
    if path.isfile(KEYFILE):
        with open(KEYFILE) as fp:
            MASTER_KEY = fp.readline()


def filter_home(params):
    # print("bismuthprice filter_home")
    if "home" in MODULES:
        namespace = params["request_handler"].get_template_namespace()
        """
        kwargs = {"api": api_filtered}
        namespace.update(kwargs)
        params["content"] += MODULES["home"].generate(**namespace)
        """
        # If you need to add extra header or footer to the home route
        # params['extra']['header'] += ' <!-- home extra header-->'
        # params['extra']['footer'] += ' <!-- home extra footer-->'
    return params
