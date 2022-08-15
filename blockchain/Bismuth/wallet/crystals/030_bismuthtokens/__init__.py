"""
Bismuth Tokens Crystal for Tornado wallet
"""

from os import path
from time import time

from modules.basehandlers import CrystalHandler
from modules.i18n import get_dt_language
from modules.helpers import base_path, get_private_dir, async_get_with_http_fallback

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/030_bismuthtokens/themes/default")

MODULES = {}

CACHED_DATA = {}
CACHED_ALL = {}

__version__ = "0.2"


async def get_data(address):
    """Query live api data or sends cached version"""
    if address in CACHED_DATA and CACHED_DATA[address][1] > time():
        # cached version still is valid
        return CACHED_DATA[address][0]
    all = await async_get_with_http_fallback("https://bismuth.today/api/tokens/")
    """
    'all': [
      ['ekn', '7bdc435229fb95321f74ead695bef31b05db0e71c4be605dc1bfc915', 21000000, 1554574309.19, 1], 
      ['ico', '7ef68a880a86ae48e077f43c509b1f959f1dd399cb8e3766e229876e', 50000, 1541578009.48, 2], 
    """
    balances = await async_get_with_http_fallback("https://bismuth.today/api/balances/{}".format(address))
    """
     'balances': [['egg', 10], ['ico', 29]]
    """
    CACHED_DATA[address] = ({"all": all, "balances": balances}, time() + 1 * 60)  # 1 min cache
    return CACHED_DATA[address][0]


class BismuthtokensHandler(CrystalHandler):

    async def about(self, params=None):
        tokens = await get_data(self.bismuth_vars['address'])
        # print(tokens)
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render(
            "about.html", bismuth=self.bismuth_vars, version=__version__, tokens=tokens
        )

    async def last(self, params=None):
        data = await get_data(self.bismuth_vars['address'])
        tokens = {}
        last = await async_get_with_http_fallback("https://bismuth.today/api/transactions/{}"
                                                  .format(self.bismuth_vars['address']))
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render(
            "last.html", bismuth=self.bismuth_vars, version=__version__, tokens=tokens, last=last
        )

    async def get(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        await getattr(self, command)(params)

    async def send_token_popup(self, params=None):
        token = self.get_argument("token", default=None, strip=False)
        print("send_token_popup {}".format(token))
        self.render("send_token_pop.html", bismuth=self.bismuth_vars, token=token)

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
