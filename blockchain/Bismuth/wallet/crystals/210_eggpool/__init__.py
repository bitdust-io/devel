"""
Dragginator Crystal for Tornado wallet
"""
from os import path, listdir
import json

from modules.basehandlers import CrystalHandler
from modules.helpers import base_path, get_api_10, graph_colors_rgba
from tornado.template import Template


__version__ = "0.1c"


DEFAULT_THEME_PATH = path.join(base_path(), "crystals/210_eggpool/themes/default")
MODULES = {}

ACTIVE = False


class EggpoolHandler(CrystalHandler):
    async def about(self, params=None):
        _ = self.locale.translate
        # print("address", self.bismuth_vars["address"])
        if len(self.bismuth_vars["address"]) > 4:
            url = "https://eggpool.net/index.php?action=api&miner={}&type=detail".format(
                self.bismuth_vars["address"]
            )
            # TODO: rewrite as async with parametrized cache ttl, see dragginator crystal
            api = get_api_10(url, is_json=True)  # gets as dict, and cache for 10 min
            print("eggpool, api", api)
        else:
            api = {}
        """
        # detail
        {'last_event': 1544822567, 
        'BIS': {'min_payout': 0, 'total_paid': 3248.8013716867, 'immature': 0.34210355367913, 'balance': 5.8549067988689}, 
        'round': {'shares': 4, 'hr': 7791, 'mhr': 7790},
        'lastround': {'mhr': 7775, 'hr': 7755, 'shares': 16}, 
        'workers': {'count': 2, 
            'detail': {
                'Hive-devrig': [3969.5, 1544822567, [3967, 3968, 3966, 3966, 3968, 3971, 3972, 3978, 3975, 3973, 3976, 3975, 3970], [6, 5, 10, 5, 13, 3, 7, 1, 8, 5, 10, 9, 2]], 
                'Egg Dev Red': [3820.5, 1544822501, [3805, 3831, 3806, 3819, 3807, 3828, 3805, 3859, 3818, 3840, 3823, 3800, 3821], [5, 4, 8, 6, 5, 6, 3, 4, 12, 5, 8, 7, 2]]}, 
                'missing_count': 0}, 
                'payouts': [['2018-12-14 08:17:14', 12.157054977414, ' '], ['2018-12-13 08:17:07', 11.277245257875, ' '], ['2018-12-12 08:17:18', 15.654745857231, ' '], ['2018-12-10 20:17:36', 11.841785656065, ' '], ['2018-12-09 20:17:18', 14.459878509432, ' '], ['2018-12-08 08:17:42', 15.839356315061, ' '], ['2018-12-06 20:17:11', 11.431415310436, ' '], ['2018-12-05 20:17:29', 16.995411304982, ' '], ['2018-12-04 08:17:35', 10.582438046254, ' '], ['2018-12-03 08:17:44', 10.179619238548, ' ']]
                }
        # v2
        {'last_event': 1544822867, 
        'BIS': {'min_payout': 0, 'total_paid': 3248.8013716867, 'immature': 0.34210355367913, 'balance': 5.8549067988689}, 
        'round': {'shares': 4, 'hr': 7791, 'mhr': 7790}, 
        'lastround': {'mhr': 7775, 'hr': 7755, 'shares': 16}, 
        'workers': {'count': 2, 
            'detail': {
                'Hive-devrig': [3969.5, 1544822867], 
                'Egg Dev Red': [3820.5, 1544822801]}, 
                'missing_count': 0}
            }

        """
        workers_name = {}
        sh_datasets = []
        hr_datasets = []
        i = 0
        gcolors = graph_colors_rgba()
        if api.get("lastround", False):
            try:
                for worker, data in api["workers"]["detail"].items():
                    # shares_series += json.dumps(data[3])+',\n'
                    rgba = gcolors[i % len(gcolors)]
                    workers_name[worker] = rgba
                    # sh_datasets.append({"label": worker, "data": data[3], "strokeColor": rgba, "borderColor": rgba})
                    sh_datasets.append({"label": worker, "data": data[3], "borderColor": rgba, "fill": False})
                    # hr_datasets.append({"label": worker, "data": data[2], "strokeColor": rgba})
                    hr_datasets.append({"label": worker, "data": data[2], "borderColor": rgba, "fill": False})
                    i += 1
            except Exception as e:
                print(e)
                workers_name[_("No data")] = gcolors[0]
        else:
            workers_name[_("No data")] = gcolors[0]

        namespace = self.get_template_namespace()
        kwargs = {
            "bismuth": self.bismuth_vars,
            "workers_name": workers_name,
            "hr_datasets": json.dumps(hr_datasets),
            "sh_datasets": json.dumps(sh_datasets),
            "version": __version__,
        }
        namespace.update(kwargs)
        self.bismuth_vars["extra"] = {
            "header": "",
            "footer": MODULES["about_charts"].generate(**namespace),
        }

        self.render(
            "about.html",
            bismuth=self.bismuth_vars,
            workers_name=workers_name,
            version=__version__,
        )

    async def get(self, command=""):
        command, *params = command.split("/")
        if not command:
            command = "about"
        if not ACTIVE:
            _ = self.locale.translate
            self.message(
                _("Error:"),
                _("This crystal is activated but needs a wallet restart."),
                "danger",
            )
        await getattr(self, command)(params)

    def get_template_path(self):
        """Override to customize template path for each handler.

        By default, we use the ``template_path`` application setting.
        Return None to load templates relative to the calling file.
        """
        return DEFAULT_THEME_PATH


def action_init(params=None):
    """Load and compiles module templates"""
    global ACTIVE
    ACTIVE = True
    modules_dir = path.join(DEFAULT_THEME_PATH, "modules")
    for module in listdir(modules_dir):
        module_name = module.split(".")[0]
        file_name = path.join(modules_dir, module)
        with open(file_name, "rb") as f:
            MODULES[module_name] = Template(f.read())


def action_unload(params=None):
    """Removes the crystal from active state"""
    global ACTIVE
    ACTIVE = False
