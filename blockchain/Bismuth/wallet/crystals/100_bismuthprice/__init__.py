"""
Bismuth Price Crystal for Tornado wallet
"""

from os import path, listdir

from modules.basehandlers import CrystalHandler
from modules.helpers import base_path, get_api_10
from tornado.template import Template

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/100_bismuthprice/themes/default")

MODULES = {}

__version__ = "0.3"

MARKETS = ["qtrade", "vinex", "graviex"]  # Markets we want to list


class BismuthpriceHandler(CrystalHandler):
    async def about(self, params=None):
        self.render("about.html", bismuth=self.bismuth_vars, version=__version__)

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
    modules_dir = path.join(DEFAULT_THEME_PATH, "modules")
    for module in listdir(modules_dir):
        module_name = module.split(".")[0]
        file_name = path.join(modules_dir, module)
        with open(file_name, "rb") as f:
            MODULES[module_name] = Template(f.read().decode("utf-8"))


def filter_home(params):
    # print("bismuthprice filter_home")
    if "home" in MODULES:
        namespace = params["request_handler"].get_template_namespace()
        """
        api = get_api_10(
            "https://bismuth.ciperyho.eu/api/markets", is_json=True
        )  # gets as dict, and cache for 10 min
        """
        api = get_api_10(
            "https://api.coingecko.com/api/v3/coins/bismuth/tickers", is_json=True
        )  # gets as dict, and cache for 10 min
        api_filtered = {}
        for market in api["tickers"]:
            # print(market)
            if market["market"]["identifier"] in MARKETS:
                if market["target"] == "BTC":
                    api_filtered[market["market"]["name"]] = (
                        market["last"],
                        market["converted_last"]["usd"],
                    )
        ponderated_btc = get_api_10(
            "https://api.coingecko.com/api/v3/simple/price?ids=bismuth&vs_currencies=btc",
            is_json=True,
        )  # gets as dict, and cache for 10 min
        ponderated_usd = get_api_10(
            "https://api.coingecko.com/api/v3/simple/price?ids=bismuth&vs_currencies=usd",
            is_json=True,
        )  # gets as dict, and cache for 10 min
        api_filtered["Ponderated"] = (
            ponderated_btc["bismuth"]["btc"],
            ponderated_usd["bismuth"]["usd"],
        )

        kwargs = {"api": api_filtered}
        namespace.update(kwargs)
        params["content"] += MODULES["home"].generate(**namespace)

        # If you need to add extra header or footer to the home route
        # params['extra']['header'] += ' <!-- home extra header-->'
        # params['extra']['footer'] += ' <!-- home extra footer-->'
    return params
