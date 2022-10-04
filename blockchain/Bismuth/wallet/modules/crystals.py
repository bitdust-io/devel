"""
Crystals manager, based upon Bismuth plugins, MIT Licence.
Copyright 2013, Michael E. Cotterell
Copyright 2018, EggPool
Copyright 2018, BismuthFoundation
"""


import collections
import importlib
import importlib.machinery
import importlib.util
import json
import logging
import sys
from os import listdir, path

from modules import helpers
from modules.helpers import base_path
from tornado.web import StaticFileHandler

__version__ = "0.3"


class CrystalManager:
    """
    A simple plugin aka crystals manager
    """

    def __init__(
        self,
        app_log=None,
        main_module="__init__",
        crystal_folder="",
        verbose=True,
        init=False,
    ):
        if app_log:
            self.app_log = app_log
        else:
            logging.basicConfig(level=logging.DEBUG)
            self.app_log = logging
        if crystal_folder == "":
            crystal_folder = path.join(helpers.base_path(), "crystals")
        self.crystal_folder = crystal_folder
        self.main_module = main_module
        self.verbose = verbose
        self.available_crystals = self.get_available_crystals()
        if self.verbose:
            self.app_log.info(
                "Available crystals: {}".format(", ".join(self.available_crystals.keys()))
            )
        self.loaded_crystals = collections.OrderedDict({})
        if init:
            self.init()

    def get_active(self):
        """Returns a dict of crystalname, active state"""
        state_filename = path.join(helpers.get_private_dir(), "crystals.json")
        states = {}
        if not path.isfile(state_filename):
            return states
        try:
            with open(state_filename, "r") as f:
                states = json.load(f)
        except:
            pass
        return states

    def _save_active(self):
        """Saves active state in the json dict for next run"""
        state_filename = path.join(helpers.get_private_dir(), "crystals.json")
        states = {
            name: name in self.loaded_crystals for name in self.available_crystals.keys()
        }
        try:
            with open(state_filename, "w") as f:
                json.dump(states, f)
        except:
            pass

    def init(self):
        """
        loads all available crystals and inits them.
        :return:
        """
        actives = self.get_active()
        for crystal in self.available_crystals:
            if actives.get(crystal, False):
                self.load_crystal(crystal)
        self.execute_action_hook("init", {"manager": self})

    def get_available_crystals(self):
        """
        Returns a dictionary of crystals available in the crystals folder
        """
        crystals = collections.OrderedDict({})
        try:
            for possible in sorted(listdir(self.crystal_folder)):
                location = path.join(self.crystal_folder, possible)
                if path.isdir(location) and self.main_module + ".py" in listdir(location):
                    info = importlib.machinery.PathFinder().find_spec(
                        self.main_module, [location]
                    )
                    about_filename = path.join(location, "about.json")
                    about = {
                        "author": "N/A",
                        "description": "N/A",
                        "email": "N/A",
                        "version": "N/A",
                        "date": "N/A",
                        "url": "N/A",
                    }
                    if path.isfile(about_filename):
                        with open(about_filename) as fp:
                            about = json.load(fp)
                    crystals[possible] = {
                        "name": possible,
                        "info": info,
                        "about": about,
                        "autoload": True,  # Todo
                    }
        except Exception as e:
            self.app_log.info(
                "Can't list crystals from '{}'.".format(self.crystal_folder)
            )
        # TODO: sort by name or priority, add json specs file.
        return crystals

    def get_loaded_crystals(self):
        """
        Returns a dictionary of the loaded crystal modules
        """
        return self.loaded_crystals.copy()

    def load_crystals(self, active_dict):
        """gets a dict of name (with priority_) , active state. returns list of newly added crystals"""
        added = []
        for name, state in active_dict.items():
            if state:
                if name not in self.loaded_crystals:
                    self.load_crystal(name)
                    module = self.loaded_crystals[name]["module"]
                    hook_func_name = "action_init"
                    if hasattr(module, hook_func_name):
                        hook_func = getattr(module, hook_func_name)
                        hook_func()
                    added.append(name)
            else:
                if name in self.loaded_crystals:
                    self.unload_crystal(name)
        self._save_active()
        # Don't, this breaks the current request
        # tornado.autoreload._reload()
        return added

    def load_crystal(self, crystal_name, active=False):
        """
        Loads a crystal module
        """
        if crystal_name in self.available_crystals:
            if crystal_name not in self.loaded_crystals:
                spec = self.available_crystals[crystal_name]["info"]
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.loaded_crystals[crystal_name] = {
                    "name": crystal_name,
                    "info": self.available_crystals[crystal_name]["info"],
                    "module": module,
                    "active": active,
                    "icon": self.available_crystals[crystal_name]["about"].get(
                        "icon", False
                    ),
                }
                if self.verbose:
                    self.app_log.info("Crystal '{}' loaded".format(crystal_name))
            else:
                self.app_log.warning("Crystal '{}' already loaded".format(crystal_name))
        else:
            self.app_log.error("Cannot locate crystal '{}'".format(crystal_name))
            raise Exception("Cannot locate crystal '{}'".format(crystal_name))

    def _unload_crystal(self, crystal_name):
        del self.loaded_crystals[crystal_name]
        if self.verbose:
            self.app_log.info("Crystal '{}' unloaded".format(crystal_name))

    def unload_crystal(self, crystal_name=""):
        """
        Unloads a single crystal module or all if crystal_name is empty
        """
        try:
            if crystal_name:
                self._unload_crystal(crystal_name)
            else:
                for crystal in self.get_loaded_crystals():
                    self._unload_crystal(crystal)
        except:
            pass

    def get_handler(self, key):
        """get a tornado handler from a single (full) name"""
        crystal_info = self.loaded_crystals[key]
        handlers = []
        try:
            module = crystal_info["module"]
            name = key.split("_")[1]
            hook_func_name = "{}Handler".format(name.capitalize())
            if hasattr(module, hook_func_name):
                hook_class = getattr(module, hook_func_name)
                handlers.append((r"/crystal/{}/(.*)".format(name), hook_class))
        except Exception as e:
            self.app_log.warning(
                "Crystal '{}' exception '{}' on get_handlers".format(key, e)
            )
        return handlers

    def get_handlers(self):
        handlers = []
        for key, crystal_info in self.loaded_crystals.items():
            try:
                module = crystal_info["module"]
                name = key.split("_")[1]
                hook_func_name = "{}Handler".format(name.capitalize())
                print(key, "hook_func_name", hook_func_name)
                if hasattr(module, hook_func_name):
                    hook_class = getattr(module, hook_func_name)
                    # Add a static handler if there is a static method
                    if hasattr(hook_class, "static"):
                        static_path = path.join(
                            base_path(), "crystals/{}/static/".format(key)
                        )
                        # print('need static', static_path)
                        handlers.append(
                            (
                                r"/crystal/{}/static/(.*)".format(name),
                                StaticFileHandler,
                                dict(path=static_path),
                            )
                        )
                    handlers.append((r"/crystal/{}/(.*)".format(name), hook_class))

            except Exception as e:
                self.app_log.warning(
                    "Crystal '{}' exception '{}' on get_handlers".format(key, e)
                )
        return handlers

    def execute_action_hook(self, hook_name, hook_params=None, first_only=False):
        """
        Executes action hook functions of the form action_hook_name contained in
        the loaded crystal modules.
        """
        for key, crystal_info in self.loaded_crystals.items():
            try:
                module = crystal_info["module"]
                hook_func_name = "action_{}".format(hook_name)
                if hasattr(module, hook_func_name):
                    hook_func = getattr(module, hook_func_name)
                    hook_func(hook_params)
                    if first_only:
                        # Avoid deadlocks on specific use cases
                        return
            except Exception as e:
                self.app_log.warning(
                    "Crystal '{}' exception '{}' on action '{}'".format(key, e, hook_name)
                )

    def execute_filter_hook(self, hook_name, hook_params, first_only=False):
        """
        Filters the hook_params through filter hook functions of the form
        filter_hook_name contained in the loaded crystal modules.
        """
        try:
            hook_params_keys = hook_params.keys()
            for key, crystal_info in self.loaded_crystals.items():
                try:
                    module = crystal_info["module"]
                    hook_func_name = "filter_{}".format(hook_name)
                    # print("looking for ", hook_func_name)
                    if hasattr(module, hook_func_name):
                        hook_func = getattr(module, hook_func_name)
                        # print(key, "hook_params", hook_params)
                        hook_params = hook_func(hook_params)
                        for nkey in hook_params_keys:
                            if nkey not in hook_params.keys():
                                msg = "Function '{}' in crystal '{}' is missing '{}' in the dict it returns".format(
                                    hook_func_name, crystal_info["name"], nkey
                                )
                                self.app_log.error(msg)
                                raise Exception(msg)
                            if first_only:
                                # Avoid deadlocks on specific use cases
                                return  # will trigger the finally section
                except Exception as e:
                    self.app_log.warning(
                        "Crystal '{}' exception '{}' on filter '{}'".format(
                            key, e, hook_name
                        )
                    )
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print(exc_type, fname, exc_tb.tb_lineno)

        except Exception as e:
            self.app_log.warning("Exception '{}' on filter '{}'".format(e, hook_name))
        finally:
            return hook_params


if __name__ == "__main__":
    print("This is the Crystals module.")
