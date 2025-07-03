#!/usr/bin/python
# deploy.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (deploy.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#
"""
..

module:: deploy

Lets keep all software related data files in one place.
AppDataDir is a location of ".bitdust" folder basically.
However you can setup your donated location in another place: USB-stick, second hard disk, etc ...

Linux: /home/$USER/.bitdust
WindowsXP: c:\\Document and Settings\\[user]\\.bitdust
Windows7 and later: c:\\Users\\[user]\\.bitdust
MacOS: /Users/$USER/.bitdust

"""

#------------------------------------------------------------------------------

import os
import sys
import platform

#------------------------------------------------------------------------------

_AppDataDirPath = None
_CurrentNetwork = None

#------------------------------------------------------------------------------


def print_text(msg, nl='\n'):
    """
    Send some output to the console.
    """
    sys.stdout.write(msg + nl)
    sys.stdout.flush()


def get_executable_location():
    """
    Returns path to the folder from where current process was executed.
    """
    try:
        source_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except:
        source_dir = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
    return source_dir


def appdata_location_file_path():
    """
    You can configure BitDust software to use another place for data folder.

    Say you want to store BitDust files on another disk. In the binary
    folder file "appdata" can be created and it will keep the path to
    the data folder.
    """
    return os.path.join(get_executable_location(), 'appdata')


def current_base_dir():
    """
    Returns currently known base location.
    """
    global _AppDataDirPath
    return _AppDataDirPath


def set_base_dir(new_path):
    """
    Rewrite currently known location of base dir with new path.
    """
    global _AppDataDirPath
    _AppDataDirPath = new_path


def current_network():
    global _CurrentNetwork
    return _CurrentNetwork


def default_base_dir_portable():
    """
    A portable method to get the default data folder location.
    """
    if platform.uname()[0] == 'Windows':
        return os.path.join(os.path.expanduser('~'), '.bitdust')

    elif platform.uname()[0] == 'Linux':
        if 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_ROOT' in os.environ:
            from android.storage import app_storage_path  # @UnresolvedImport
            return os.path.join(app_storage_path(), '.bitdust')

        return os.path.join(os.path.expanduser('~'), '.bitdust')

    elif platform.uname()[0] == 'Darwin':
        return os.path.join(os.path.expanduser('~'), '.bitdust')

    elif 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_ROOT' in os.environ:
        from android.storage import app_storage_path  # @UnresolvedImport
        return os.path.join(app_storage_path(), '.bitdust')

    return os.path.join(os.path.expanduser('~'), '.bitdust')


def init_current_network(name=None, base_dir=None):
    global _CurrentNetwork
    base_dir = base_dir or current_base_dir()
    if name:
        if name == 'current_network':
            raise Exception('invalid network name')
        _CurrentNetwork = name
        open(os.path.join(base_dir, 'current_network'), 'w').write(_CurrentNetwork)
        return
    if _CurrentNetwork:
        return
    try:
        cur_network = open(os.path.join(base_dir, 'current_network'), 'r').read().strip()
    except:
        cur_network = 'default'
    if not cur_network:
        cur_network = 'default'
    if not os.path.isdir(os.path.join(base_dir, cur_network)):
        cur_network = 'default'
    _CurrentNetwork = cur_network
    open(os.path.join(base_dir, 'current_network'), 'w').write(_CurrentNetwork)


def init_base_dir(base_dir=None, network_name=None):
    """
    Do some validation and create needed data folders if they are not exist
    yet.

    You can specify another location for data files.
    """
    global _AppDataDirPath
    global _CurrentNetwork

    # if we already know the place - we are done
    if base_dir:
        _AppDataDirPath = base_dir
        if not os.path.exists(_AppDataDirPath):
            os.makedirs(_AppDataDirPath, 0o777)
        init_current_network(name=network_name)
        return _AppDataDirPath

    # if location was already known - no need to check again
    if _AppDataDirPath is not None:
        init_current_network(name=network_name)
        return _AppDataDirPath

    # if we have a file "appdata" in current folder - read location path from there
    appdata_path = appdata_location_file_path()
    if os.path.isfile(appdata_path):
        if os.path.isfile(appdata_path) and os.access(appdata_path, os.R_OK):
            infile = open(appdata_path, 'r')
            path = infile.read().strip()
            infile.close()
            if path:
                path = os.path.abspath(path)
                if not os.path.isdir(path):
                    os.makedirs(path, 0o777)
                _AppDataDirPath = path
                init_current_network(name=network_name)
                return _AppDataDirPath

    # get the default place for that machine
    default_path = default_base_dir_portable()

    # we can use folder ".bitdust" placed on the same level with binary folder:
    # /..
    #   /.bitdust - data files
    #   /bitdust  - source files
    path1 = str(os.path.abspath(os.path.join(get_executable_location(), '..', '.bitdust')))
    # and default path will have lower priority
    path2 = default_path

    # if default path exists - use it
    if os.path.isdir(path2):
        _AppDataDirPath = path2
    # but ".bitdust" folder on same level will have higher priority
    if os.path.isdir(path1):
        _AppDataDirPath = path1
    # use default path if nothing existing yet
    if not _AppDataDirPath:
        _AppDataDirPath = default_path

    # if we did not found "current_network" file - use default path, new copy of BitDust
    if not os.path.isdir(os.path.join(current_base_dir(), 'current_network')):
        _AppDataDirPath = path2
        if not os.path.exists(_AppDataDirPath):
            os.makedirs(_AppDataDirPath)
        init_current_network(name=network_name)
        return _AppDataDirPath

    # if we did not found our key - use default path, new copy of BitDust
    if not os.access(os.path.join(current_base_dir(), current_network(), 'metadata', 'mykeyfile'), os.R_OK) or \
        not os.access(os.path.join(current_base_dir(), current_network(), 'metadata', 'mykeyfile_location'), os.R_OK):
        _AppDataDirPath = path2
        if not os.path.exists(_AppDataDirPath):
            os.makedirs(_AppDataDirPath, 0o777)
        init_current_network(name=network_name)
        return _AppDataDirPath

    # if we did not found our identity - use default path, new copy of BitDust
    if not os.access(os.path.join(current_base_dir(), current_network(), 'metadata', 'localidentity'), os.R_OK):
        _AppDataDirPath = path2
        if not os.path.exists(_AppDataDirPath):
            os.makedirs(_AppDataDirPath)
        init_current_network(name=network_name)
        return _AppDataDirPath

    init_current_network(name=network_name)
    # seems we found needed files in a path1 - let us use this as a base dir
    return _AppDataDirPath


#------------------------------------------------------------------------------


def run(args):
    """
    Creates virtual environment
    """
    status = 1
    on_windows = platform.uname()[0] == 'Windows'
    on_mac = platform.uname()[0] == 'Darwin'
    on_linux = platform.uname()[0] == 'Linux'
    source_dir = get_executable_location()
    init_base_dir()
    base_dir = current_base_dir()
    if on_windows and os.path.isfile(os.path.join(base_dir, 'shortpath.txt')):
        base_dir = open(os.path.join(base_dir, 'shortpath.txt')).read().strip()
    venv_path = os.path.join(base_dir, 'venv')
    if len(args) > 1 and not os.path.exists(args[1]) and os.path.isdir(os.path.dirname(args[1])):
        venv_path = args[1]
    pip_bin = '{}/bin/pip'.format(venv_path)
    script_path = os.path.join(base_dir, 'bitdust')

    if os.path.exists(venv_path):
        print_text('\n***** Clean up existing Python virtual environment in "%s"' % venv_path)
        if on_windows:
            status = os.system('rmdir /S /Q "{}"'.format(venv_path))
        else:
            status = os.system('rm -rf {}'.format(venv_path))
        if status != 0:
            print_text('\n***** Clean up of existing virtual environment files failed!\n')
            return status

    current_python = sys.executable
    print_text('\n***** Current Python executable is {}'.format(current_python))

    print_text('\n***** Creating virtual environment in "%s"' % venv_path)
    make_venv_cmd = 'virtualenv -p {} {}'.format(current_python, venv_path)
    if on_windows:
        python_exe = '"%s"' % os.path.join(base_dir, 'python', 'python.exe')
        if not os.path.exists(python_exe):
            python_exe = current_python
        make_venv_cmd = '{} -m virtualenv --system-site-packages {}'.format(python_exe, venv_path)
    if on_mac:
        if sys.version_info >= (3, 11):
            make_venv_cmd = '{} -m venv --clear --copies {}'.format(current_python, venv_path)
        else:
            make_venv_cmd = '{} -m virtualenv --clear --always-copy {}'.format(current_python, venv_path)

    print_text('\n***** Executing "{}"'.format(make_venv_cmd))
    status = os.system(make_venv_cmd)
    if on_mac and status != 0:
        make_venv_cmd = 'virtualenv -p {} {}'.format(current_python, venv_path)
        status = os.system(make_venv_cmd)
    if on_linux and status != 0:
        make_venv_cmd = '{} -m pip install -q virtualenv'.format(current_python)
        status = os.system(make_venv_cmd)
        make_venv_cmd = '{} -m virtualenv --clear --always-copy {}'.format(current_python, venv_path)
        status = os.system(make_venv_cmd)

    if status != 0:
        print_text('\n***** Failed to create virtual environment, please check/install virtualenv package\n')
        print_text('\n***** Please try to install virtualenv package manually:\n')
        print_text('    {} -m pip install virtualenv\n\n'.format(current_python))
        return status

    if on_windows or on_mac:
        pass
    else:
        print_text('\n***** Installing/Upgrading pip in "%s"' % venv_path)
        status = os.system('{} install -U pip'.format(pip_bin))
        if status != 0:
            # print_text('\n***** Failed to install latest pip version, please check/install latest pip version manually\n')
            # return status
            pass

    if on_mac:
        print_text('\n***** Updating setuptools version in "%s"' % venv_path)
        status = os.system('{} install setuptools'.format(pip_bin))
        if status != 0:
            print_text('\n***** Failed to install/upgrade setuptools, please check/install setuptools manually\n')
            return status

    requirements_txt = os.path.join(source_dir, 'requirements.txt')
    print_text('\n***** Installing BitDust requirements from "%s"' % (requirements_txt))
    requirements_cmd = '{} install -q -r "{}"'.format(pip_bin, requirements_txt)
    if on_windows:
        venv_python_path = os.path.join(base_dir, 'venv', 'Scripts', 'python.exe')
        requirements_cmd = '{} -m pip install -q -r "{}"'.format(venv_python_path, requirements_txt)
    if on_mac:
        venv_python_path = os.path.join(base_dir, 'venv', 'bin', 'python')
        requirements_cmd = '{} -m pip install -q -r "{}"'.format(venv_python_path, requirements_txt)

    print_text('\n***** Executing "{}"'.format(requirements_cmd))
    status = os.system(requirements_cmd)

    if on_windows and status == 0:
        extra_requirements_cmd = '{} -m pip install -q pywin32 pypiwin32'.format(venv_python_path)
        status = os.system(extra_requirements_cmd)

    if status != 0:
        # TODO: try to detect package manager on target OS and give more correct info: debian/mandrake/OSX
        # TODO: on Windows it could be that some of the .wheels are not available - need to provide a different message
        depends = [
            'gcc',
            'build-essential',
            'libssl-dev',
            'libffi-dev',
            'python3-dev',
            'python3-virtualenv',
        ]
        print_text('\n***** Please try to install those binary packages manually:\n')
        print_text('    %s\n\n' % (' '.join(depends)))
        return status

    # TODO: on Windows this script should create .bat file instead
    script = u'#!/bin/sh\n'
    script += u'# This is a short shell script to create an alias in OS for BitDust software.\n'
    script += u'# NOTICE: BitDust software do not require root permissions to run, please start it as normal user.\n\n'
    script += u'{}/bin/python {}/bitdust.py "$@"\n\n'.format(venv_path, source_dir)
    fil = open(script_path, mode='w')
    fil.write(script)
    fil.close()
    os.chmod(script_path, 0o775)
    print_text('\n***** BitDust app files created successfully in {}\n'.format(base_dir))
    print_text('To run BitDust you can use this executable file:\n\n    {}\n\n'.format(script_path))
    print_text('To create system-wide shell command you can add folder {} to your PATH:\n'.format(base_dir))
    print_text('    export PATH="$PATH:{}"\n\n'.format(base_dir))
    print_text('Once you set a system-wide alias for BitDust, you are invited to learn more about the software via the command line:\n\n    bitdust help\n\n')
    print_text('Visit BitDust Wiki on-line page:\n\n    www.bitdust.io/wiki\n\n')
    print_text('Welcome to BitDust!\n\n')
    return 0
