"""
Dragginator Crystal for Tornado wallet
"""
from os import path, listdir
import sys

from modules.basehandlers import CrystalHandler
from modules.i18n import get_dt_language
from modules.helpers import base_path, async_get_with_http_fallback
from tornado.template import Template

__version__ = '0.2b'

DEFAULT_THEME_PATH = path.join(base_path(), 'crystals/250_autogame/themes/default')

MODULES = {}


class AutogameHandler(CrystalHandler):

    """
    def initialize(self):
        super().initialize()
        self.bismuth_vars['extra'] = {"header":'<!-- Autogame HEADER -->', "footer": '<!-- Autogame FOOTER -->'}
    """

    async def about(self, params=None):
        games_detail = {}
        if len(self.bismuth_vars['address']) == 56:
            # self.bismuth_vars['address'] = 'fefb575972cd8fdb086e2300b51f727bb0cbfc33282f1542e19a8f1d'  # debug
            url = "http://autogame.bismuth.live:6060/api/seed/{}".format(self.bismuth_vars['address'])
            # print(url)
            games_list = await async_get_with_http_fallback(url)
            # print(games_list)
            if games_list is None or len(games_list) == 0:
                # games_list = ['da67c4db9d995c49cec1', '54c0f5571e69e26375db']
                games_list = []
            # TODO: cache
            for game in games_list:
                url = "http://autogame.bismuth.live:6060/api/db/{}".format(game)
                status = await async_get_with_http_fallback(url)
                try:
                    games_detail[game] = status
                except:
                    pass
        else:
            games_list = []
        # We need the namespace to use modules (sub templates), like here to inject custom JS in the footer.
        namespace = self.get_template_namespace()
        self.bismuth_vars['extra'] = {"header": '', "footer": MODULES['footer'].generate(**namespace)}
        self.render("about.html", bismuth=self.bismuth_vars, version=__version__, games_list=games_list,
                    games_detail=games_detail)

    async def replay_pop(self, params=None):
        """replay, in a template without base content"""
        hash = self.get_argument("hash", None)
        url = "http://autogame.bismuth.live:6060/api/replay/{}".format(hash)
        actions = await async_get_with_http_fallback(url)
        self.render("replay_pop.html", bismuth=self.bismuth_vars, hash=hash, actions=actions)

    async def status_pop(self, params=None):
        """status of a game, in a template without base content"""
        hash = self.get_argument("hash", None)
        url = "http://autogame.bismuth.live:6060/api/db/{}".format(hash)
        status = await async_get_with_http_fallback(url)
        self.render("status_pop.html", bismuth=self.bismuth_vars, hash=hash, status=status)

    async def get(self, command=''):
        command, *params = command.split('/')
        if not command:
            command = 'about'
        await getattr(self, command)(params)

    def get_template_path(self):
        """Override to customize template path for each handler."""
        return DEFAULT_THEME_PATH


def action_init(params=None):
    """Load and compiles module templates"""
    modules_dir = path.join(DEFAULT_THEME_PATH, 'modules')
    for module in listdir(modules_dir):
        module_name = module.split('.')[0]
        file_name = path.join(modules_dir, module)
        with open(file_name, 'rb') as f:
            MODULES[module_name] = Template(f.read())


def filter_home(params):
    try:
        if 'home' in MODULES:
            namespace = params['request_handler'].get_template_namespace()
            params["content"] += MODULES['home'].generate(**namespace)
        return params
    except Exception as e:
        print(str(e))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
