#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_localsite.settings")
    pth = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    sys.path.insert(0, pth)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
