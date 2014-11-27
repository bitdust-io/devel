import sys, os

__doc__ = """
This code comes from Shtoom: http://divmod.org/projects/shtoom
Copyright (C) 2004 Anthony Baxter
Licensed under the GNU LGPL.
"""

if 1:
    # Enables "import shtoom.stuff" instead of "import lib.shtoom.stuff"
    _lib_path = os.path.split(os.path.dirname(__file__))[0]
    if _lib_path not in sys.path:
        sys.path.append(_lib_path)

