"""
Hello World Crystal for Tornado wallet
"""

import json
import time
from os import path
from modules.helpers import async_get_with_http_fallback
from modules.basehandlers import CrystalHandler
from modules.helpers import base_path

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/101_helloworld/themes/default")

MODULES = {}

__version__ = "1.0.0"

class HelloworldHandler(CrystalHandler):
    #def initialize(self):
        # This method is not needed if you don't need custom init code,
        # else include it and add your own code after super()...
        #super().initialize()

    async def about(self, params=None):
        self.render("about.html", bismuth=self.bismuth_vars)

    async def message_popup(self, params=None):
        title = self.get_argument("title", default=None, strip=False)
        message = self.get_argument("msg", default=None, strip=False)
        type = self.get_argument("type", default=None, strip=False)
        self.render("message_pop.html", bismuth=self.bismuth_vars, title=title, message=message, type=type)
        
    async def page1(self, params=None):
        data = {}
        data['txs'] = {}
        data['hns'] = {}
        data['msg'] = {}

        button1 = self.get_argument("button1", default=None, strip=False)
        if button1 is not None:
            data['txs'] = self.bismuth.latest_transactions(5, for_display=True, mempool_included=True)

        button2 = self.get_argument("button2", default=None, strip=False)
        if button2 is not None:
            data['hns'] = await async_get_with_http_fallback("https://hypernodes.bismuth.live/status.json")

        button3 = self.get_argument("button3", default=None, strip=False)
        if button3 is not None:
            data['msg'] = self.get_argument("mytext", default=None, strip=False)
            self.render(
                "message_pop.html",
                bismuth=self.bismuth_vars,
                title="My Title",
                message=data['msg'],
                type="info",
            )
            return

        self.render("page1.html", bismuth=self.bismuth_vars, data=data)

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
