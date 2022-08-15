"""
Docshield Crystal for Tornado wallet
"""

from os import path, listdir

# import sys

from modules.basehandlers import CrystalHandler
from modules.i18n import get_dt_language
from modules.helpers import base_path

# from tornado.template import Template


DEFAULT_THEME_PATH = path.join(base_path(), "crystals/212_docshield/themes/default")

MODULES = {}

__version__ = "1.0.5"


class DocshieldHandler(CrystalHandler):
    def initialize(self):
        # Parent init
        super().initialize()
        """
        # DEPRECATED, see footer block in about .html instead.
        # Inject our local js file in the template footer, so js code is seen after jquery
        js_inject_file_path = path.join(DEFAULT_THEME_PATH, "docshield.js")  # Never use relative file paths
        with open(js_inject_file_path) as file:
            data = file.read()
        """
        data = ""
        self.bismuth_vars["extra"] = {
            "header": "<!-- DOCHASH HEADER -->",
            "footer": data,
        }

    async def about(self, params=None):
        namespace = self.get_template_namespace()
        self.bismuth_vars["dtlanguage"] = get_dt_language(self.locale.translate)
        kwargs = {"bismuth": self.bismuth_vars}
        namespace.update(kwargs)
        self.render("about.html", bismuth=self.bismuth_vars)

    async def get(self, command=""):
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


"""
def action_init(params=None):
    #Load and compiles module templates
    modules_dir = path.join(DEFAULT_THEME_PATH, 'modules')
    # No modules for this crystal, so can be ignored.
    for module in listdir(modules_dir):
        module_name = module.split('.')[0]
        file_name = path.join(modules_dir, module)
        with open(file_name, 'rb') as f:
            MODULES[module_name] = Template(f.read())


def filter_home(params):
    try:
        # No module to display on the home screen, left for reference only.
        if 'home' in MODULES:
            namespace = params['request_handler'].get_template_namespace()
            params["content"] += MODULES['home'].generate(**namespace)
        return params
    except Exception as e:
        print(str(e))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
"""
