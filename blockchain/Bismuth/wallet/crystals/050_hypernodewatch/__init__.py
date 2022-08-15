"""
Hypernode watch Crystal for Tornado wallet
"""

from os import path, listdir

from modules.basehandlers import CrystalHandler
from modules.helpers import base_path
from tornado.template import Template

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/050_hypernodewatch/themes/default")

MODULES = {}

__version__ = "0.1"


class HypernodewatchHandler(CrystalHandler):
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
