"""
Phone Battery Crystal for Tornado wallet
"""

import sys
import time
from os import path
from modules.basehandlers import CrystalHandler
from modules.i18n import get_dt_language
from modules.helpers import base_path
from modules.helpers import async_get_with_http_fallback

sys.path.append('crystals/400_phonebattery')
from bismuthsimpleasset import BismuthSimpleAsset
from phoneapihandler import PhoneAPIHandler

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/400_phonebattery/themes/default")

MODULES = {}

__version__ = "1.0.0"

class PhonebatteryHandler(CrystalHandler):
    def initialize(self):
        # Parent init
        super().initialize()
        data = ""
        self.bismuth_vars["extra"] = {
            "header": "<!-- PHONEBATTERY HEADER -->",
            "footer": data,
        }
        reg = "phone:register"
        unreg = "phone:unregister"
        transfer = "phone:transfer"
        op_data = "phone:battery"

        self.phonehandler = PhoneAPIHandler(self.bismuth,reg,unreg,op_data)
        address = "Bis1QPHone8oYrrDRjAFW1sNjyJjUqHgZhgAw"
        thresholds = {"reg": 5}
        checkfunc = {"f": self.phonehandler.checkID}
        self.assethandler = BismuthSimpleAsset(self.bismuth,address,reg,unreg,transfer,thresholds,checkfunc)

    async def message_popup(self, params=None):
        title = self.get_argument("title", default=None, strip=False)
        message = self.get_argument("msg", default=None, strip=False)
        type = self.get_argument("type", default=None, strip=False)
        self.render("message_pop.html", bismuth=self.bismuth_vars, title=title, message=message, type=type)

    async def about(self, params=None):
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render("about.html", bismuth=self.bismuth_vars)

    async def fetch_asset_id(self, params=None):
        """"
        Fetch asset ID using termux-api
        """
        pwd = self.get_argument("pwd", default=None, strip=False)
        data = self.phonehandler.asset_id(pwd)
        self.render("json.html", data=data)

    async def fetch_api_data(self, params=None):
        """
        Returns a dict with asset data
        """
        pwd = self.get_argument("pwd", default=None, strip=False)
        out = self.phonehandler.fetch_asset_data(pwd)
        self.render("json.html", data=out)

    async def check_id_register(self, params=None):
        """
        Checks if an asset id is valid and registered
        """
        asset_id = self.get_argument("asset_id", default=None, strip=False)
        # First check if this is a valid asset ID
        data = self.phonehandler.checkID(asset_id)
        if data != -1:
            # Second check if asset ID is already registered
            registrant = self.assethandler.get_registrant(asset_id)
            if len(registrant) > 0:
                data = -1
        self.render("json.html", data=data)

    async def check_id_unregister(self, params=None):
        """
        Unregisters asset ID if valid and current address has previously registered it
        """
        asset_id = self.get_argument("asset_id", default=None, strip=False)
        # First check if this is a valid asset ID
        data = self.phonehandler.checkID(asset_id)
        if data != -1:
            # Second check if this account has registered this asset ID
            registrant = self.assethandler.get_registrant(asset_id)
            if registrant != self.bismuth.address:
                data = -1
        self.render("json.html", data=data)

    async def get_all_asset_ids(self, params=None):
        asset_search = self.get_argument("asset_search", default=None, strip=False)
        out = self.assethandler.get_all_asset_ids(asset_search)
        self.render("json.html", data=out)

    async def get_chain_data(self, params=None):
        """
        Returns asset data as specified by 'variable' between start and end dates
        Used for displaying data by DataTable and ChartJS
        """
        addresses = self.get_argument("address", default=None, strip=False)
        asset_id = self.get_argument("asset_id", default=None, strip=False)
        variable = self.get_argument("variable", default=None, strip=False)
        temperature = self.get_argument("temperature", default=None, strip=False)
        startdate = self.get_argument("startdate", default=None, strip=False)
        enddate = self.get_argument("enddate", default=None, strip=False)
        if variable == "battery_cycles":
            out = self.phonehandler.get_cycle_data(addresses,asset_id,"percentage",temperature,startdate,enddate)
        else:
            out = self.phonehandler.get_chain_data(addresses,asset_id,variable,temperature,startdate,enddate)
        self.render("json.html", data=out)

    async def page1(self, params=None):
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render("page1.html", bismuth=self.bismuth_vars)

    async def page2(self, params=None):
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render("page2.html", bismuth=self.bismuth_vars)

    async def page3(self, params=None):
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render("page3.html", bismuth=self.bismuth_vars)

    async def get(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        await getattr(self, command)(params)

    async def post(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        await getattr(self, command)(params)

    def get_template_path(self):
        """Override to customize template path for each handler."""
        return DEFAULT_THEME_PATH

    def static(self):
        """Defining this method will automagically create a static handler pointing to local /static crystal dir"""
        pass
