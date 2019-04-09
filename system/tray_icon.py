#!/usr/bin/python
# tray_icon.py
#
#
# Copyright (C) 2008-2019 Veselin Penev, https://bitdust.io
#
# This file (tray_icon.py) is part of BitDust Software.
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
#

"""
.. module:: tray_icon.

Uses wxPython to show tray icon for BitDust. This is working inside
``bpmain`` process, uses wxreactor to connect with main Twisted loop.
"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import platform

#------------------------------------------------------------------------------

USE_TRAY_ICON = True
LABEL = 'BitDust'

_IconObject = None
_ControlFunc = None
_CurrentIcon = 'off'

_IconsDict = {}

_LinuxIcons = {
    'off': 'off24x24.png',
    'connected': 'connected24x24.png',
    'sync': 'sync24x24.png',
    'error': 'error24x24.png',
    'updated': 'updated24x24.png',
}

_WindowsIcons = {
    'off': 'off16x16.png',
    'connected': 'connected16x16.png',
    'sync': 'sync16x16.png',
    'error': 'error16x16.png',
    'updated': 'updated16x16.png',
}

_PopUpIconsDict = {
    'open': 'expand24x24.png',
    'sync': 'synchronize24x24.png',
    'restart': 'restart24x24.png',
    'reconnect': 'network24x24.png',
    'shutdown': 'shutdown24x24.png',
}

#------------------------------------------------------------------------------


def icons_dict():
    global _IconsDict
    return _IconsDict


def popup_icons_dict():
    global _PopUpIconsDict
    return _PopUpIconsDict

#------------------------------------------------------------------------------


def shutdown():
    global _IconObject
    global USE_TRAY_ICON
    if not USE_TRAY_ICON:
        return
    if _IconObject:
        try:
            _IconObject.Destroy()
        except:
            pass
        del _IconObject
        _IconObject = None


def init(icons_path, icons_files=None):
    global _IconObject
    global _IconsDict
    global USE_TRAY_ICON
    if not USE_TRAY_ICON:
        return

    if icons_files:
        _IconsDict = icons_files
    else:
        if platform.uname()[0] == 'Linux' or platform.uname()[0] == 'Darwin':
            _IconsDict = _LinuxIcons
        else:
            _IconsDict = _WindowsIcons

    import wx

    from twisted.internet import reactor  # @UnresolvedImport

    def create_menu_item(menu, label, func, icon=None):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        if icon is not None:
            item.SetBitmap(icon)
        menu.AppendItem(item)
        return item

    class MyTaskBarIcon(wx.TaskBarIcon):

        def __init__(self, icons_path, current_icon_name=None):
            super(MyTaskBarIcon, self).__init__()
            self.icons_path = icons_path
            self.icons = {}
            self.popup_icons = {}
            for name, filename in icons_dict().items():
                self.icons[name] = wx.IconFromBitmap(wx.Bitmap(os.path.join(icons_path, filename)))
            for name, filename in popup_icons_dict().items():
                self.popup_icons[name] = wx.Bitmap(os.path.join(icons_path, filename))
            if len(self.icons) == 0:
                self.icons['default'] = ''
            if current_icon_name is not None and current_icon_name in list(self.icons.keys()):
                self.current = current_icon_name
            else:
                self.current = list(self.icons.keys())[0]
            self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
            self.select_icon(self.current)

        def CreatePopupMenu(self):
            menu = wx.Menu()
            create_menu_item(menu, 'open', self.on_show, self.popup_icons.get('open', None))
            create_menu_item(menu, 'synchronize', self.on_sync, self.popup_icons.get('sync', None))
            create_menu_item(menu, 'reconnect', self.on_reconnect, self.popup_icons.get('reconnect', None))
            create_menu_item(menu, 'restart', self.on_restart, self.popup_icons.get('restart', None))
            create_menu_item(menu, 'exit', self.on_exit, self.popup_icons.get('shutdown', None))
            self.menu = menu
            return menu

        def on_left_down(self, event):
            control('show')

        def on_show(self, event):
            control('show')

        def on_sync(self, event):
            control('sync')

        def on_hide(self, event):
            control('hide')

        def on_restart(self, event):
            control('restart')

        def on_exit(self, event):
            control('exit')

        def on_reconnect(self, event):
            control('reconnect')

        def on_toolbar(self, event):
            control('toolbar')

        def select_icon(self, icon_name):
            # print 'select_icon', icon_name, self.icons
            if icon_name in list(self.icons.keys()):
                self.current = icon_name
                self.SetIcon(self.icons.get(self.current, list(self.icons.values())[0]), LABEL)

        def clear_icon(self):
            self.RemoveIcon()

    class MyApp(wx.App):

        def __init__(self, icons_path):
            self.icons_path = icons_path
            wx.App.__init__(self, False)

        def OnInit(self):
            self.trayicon = MyTaskBarIcon(self.icons_path)
            print('OnInit')
            return True

        def OnExit(self):
            print('OnExit')
            try:
                self.trayicon.Destroy()
            except:
                pass

        def SetIcon(self, name):
            # if self.trayicon.IsAvailable():
            print('try')
            self.trayicon.select_icon(name)
            print('ok')

        def Stop(self):
            self.trayicon.clear_icon()
            try:
                self.trayicon.Destroy()
            except:
                pass

    _IconObject = MyApp(icons_path)
    reactor.registerWxApp(_IconObject)
    reactor.addSystemEventTrigger('before', 'shutdown', main_porcess_stopped)


def main_porcess_stopped():
    global _IconObject
    print('main_porcess_stopped', _IconObject)
    if _IconObject:
        try:
            _IconObject.Stop()
        except:
            pass
        del _IconObject
        _IconObject = None

#------------------------------------------------------------------------------


def control(cmd):
    print('control', cmd)
    global _ControlFunc
    if _ControlFunc is not None:
        _ControlFunc(cmd)


def draw_icon(name):
    global _IconObject
    if _IconObject is not None:
        _IconObject.SetIcon(name)


def set_icon(name):
    global _CurrentIcon
    _CurrentIcon = name
    draw_icon(name)


def restore_icon():
    global _CurrentIcon
    draw_icon(_CurrentIcon)


def state_changed(network, p2p):
    # print 'state_changed', network, p2p
    if [network, p2p, ].count('CONNECTED') == 2:
        set_icon('connected')
        return
    # if network == 'DISCONNECTED':
    #     set_icon('off')
    #     return
    # if network == 'CONECTED' and p2p == 'DISCONNECTED':
    #     set_icon('red')
    #     return
    # if [ network, p2p ].count('CONNECTED') == 1:
    #     set_icon('yellow')
    #     return
    set_icon('off')


def SetControlFunc(f):
    global _ControlFunc
    _ControlFunc = f

#------------------------------------------------------------------------------

if __name__ == "__main__":
    def test_control(cmd):
        print('test_control', cmd)
        if cmd == 'exit':
            reactor.stop()
            print('reactor stopped')
            # os._exit(0)
            # sys.exit()

    from twisted.internet import wxreactor
    wxreactor.install()
    from twisted.internet import reactor  # @UnresolvedImport
    init(sys.argv[1])
    SetControlFunc(test_control)
    reactor.run()
