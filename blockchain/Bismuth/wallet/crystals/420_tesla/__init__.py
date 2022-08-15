"""
Tesla Crystal for Tornado wallet
"""

import sys
import time
from os import path
from modules.basehandlers import CrystalHandler
from modules.i18n import get_dt_language
from modules.helpers import base_path
from modules.helpers import async_get_with_http_fallback

sys.path.append('crystals/420_tesla')
from bismuthsimpleasset import BismuthSimpleAsset
from teslaapihandler import TeslaAPIHandler

DEFAULT_THEME_PATH = path.join(base_path(), "crystals/420_tesla/themes/default")

MODULES = {}

__version__ = "1.0.0"

class TeslaHandler(CrystalHandler):
    def initialize(self):
        # Parent init
        super().initialize()
        data = ""
        self.bismuth_vars["extra"] = {
            "header": "<!-- TESLA HEADER -->",
            "footer": data,
        }
        reg = "tesla:register"
        unreg = "tesla:unregister"
        transfer = "tesla:transfer"
        op_data = "tesla:battery"

        self.teslahandler = TeslaAPIHandler(self.bismuth,reg,unreg,op_data)
        address = "Bis1TeSLaWhTC2ByEwZnYWtsPVK5428uqnL46"
        thresholds = {"reg": 25}
        checkfunc = {"f": self.teslahandler.checkID}
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
        Fetch asset ID associated with email address. pwd is the vehicle anonymizer
        """
        email = self.get_argument("email", default=None, strip=False)
        pwd = self.get_argument("pwd", default=None, strip=False) #For XOR
        data = self.teslahandler.tesla_vins(email, pwd)
        time.sleep(1)
        self.render("json.html", data=data)

    async def fetch_api_data(self, params=None):
        """
        Returns a dict with vehicle data for all VINs associated with email and anonymizer
        """
        email = self.get_argument("email", default=None, strip=False)
        pwd = self.get_argument("pwd", default=None, strip=False) #For XOR
        out = self.teslahandler.fetch_vehicle_data(email,pwd)
        self.render("json.html", data=out)

    async def check_vin_registrant(self, params=None):
        """
        Returns registrant given asset id (vin number in vin_input)
        """
        vin = self.get_argument("vin_input", default=None, strip=False)
        # First check if this is a valid VIN
        data = self.teslahandler.checkVIN(vin)
        if data != -1:
            # Second check if active wallet address is registrant
            data = -1
            registrant = self.assethandler.get_registrant(vin)
            if registrant == self.bismuth.address:
                data = 1
        self.render("json.html", data=registrant)

    async def check_vin_register(self, params=None):
        """
        Checks if an asset id (VIN number) is valid and registered
        """
        vin = self.get_argument("vin_input", default=None, strip=False)
        # First check if this is a valid VIN
        data = self.teslahandler.checkID(vin)
        if data != -1:
            # Second check if VIN is already registered
            registrant = self.assethandler.get_registrant(vin)
            if len(registrant) > 0:
                data = -1
        self.render("json.html", data=data)

    async def check_vin_unregister(self, params=None):
        """
        Unregisters VIN if valid and current address has previously registered it
        """
        vin = self.get_argument("vin_input", default=None, strip=False)
        # First check if this is a valid VIN
        data = self.teslahandler.checkID(vin)
        if data != -1:
            # Second check if this account has registered this VIN
            registrant = self.assethandler.get_registrant(vin)
            if registrant != self.bismuth.address:
                data = -1
        self.render("json.html", data=data)

    async def get_chain_data(self, params=None):
        """
        Returns vehicle data as specified by 'variable' between start and end dates
        Used for displaying data by DataTable and ChartJS
        """
        vin = self.get_argument("vin", default=None, strip=False)
        addresses = self.get_argument("address", default=None, strip=False)
        variable = self.get_argument("variable", default=None, strip=False)
        filter = self.get_argument("filter", default=None, strip=False)
        range_unit = self.get_argument("range", default=None, strip=False)
        temperature = self.get_argument("temperature", default=None, strip=False)
        startdate = self.get_argument("startdate", default=None, strip=False)
        enddate = self.get_argument("enddate", default=None, strip=False)
        if variable == "battery_cycles":
            out = self.teslahandler.get_cycle_data(vin,addresses,"battery_level",filter,range_unit,temperature,startdate,enddate)
        else:
            out = self.teslahandler.get_chain_data(vin,addresses,variable,filter,range_unit,temperature,startdate,enddate)
        self.render("json.html", data=out)

    async def get_all_asset_ids(self, params=None):
        asset_search = self.get_argument("asset_search", default=None, strip=False)
        out = self.assethandler.get_all_asset_ids(asset_search)
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
