#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    # assume we run from /bitdust/web/
    sys.path.insert(0, os.path.abspath('..'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "asite.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
