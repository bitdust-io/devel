#!/usr/bin/python
#tray_icon.py
#
#
# <<<COPYRIGHT>>>
#
#
#
#
#

"""
.. module:: tray_icon

Uses wxPython to show tray icon for BitDust.
This is working inside ``bpmain`` process, uses wxreactor to connect with main Twisted loop.
"""

import os
import sys

USE_TRAY_ICON = False # True
LABEL = 'BitDust'
    
_IconObject = None
_ControlFunc = None

_IconsDict = {
    'red':      'icon-red-24x24.png',
    'green':    'icon-green-24x24.png',
    'gray':     'icon-gray-24x24.png',
    'yellow':   'icon-yellow-24x24.png',
}

#------------------------------------------------------------------------------ 

def init(icons_path, icons_files=None):
    global _IconObject
    global _IconsDict
    global USE_TRAY_ICON
    if not USE_TRAY_ICON:
        return
    
    if icons_files:
        _IconsDict = icons_files

    import wx
    
    from twisted.internet import reactor

    def create_menu_item(menu, label, func, icon=None):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        if icon is not None:
            item.SetBitmap(wx.Bitmap(icon))
        menu.AppendItem(item)
        return item
    
    def icons_dict():
        global _IconsDict
        return _IconsDict
    
    class MyTaskBarIcon(wx.TaskBarIcon):
        def __init__(self, icons_path, current_icon_name=None):
            super(MyTaskBarIcon, self).__init__()
            self.icons_path = icons_path
            self.icons = {}
            for name, filename in icons_dict().items():
                self.icons[name] = wx.IconFromBitmap(wx.Bitmap(os.path.join(icons_path, filename)))
            if len(self.icons) == 0:
                self.icons['default'] = ''
            if current_icon_name is not None and current_icon_name in self.icons.keys():
                self.current = current_icon_name
            else:                
                self.current = self.icons.keys()[0]
            self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
            self.select_icon(self.current)

        def items_dict(self):
            return {
                'show':     os.path.join(self.icons_path, 'expand24x24.png'),
                'hide':     os.path.join(self.icons_path, 'collapse24x24.png'),
                'toolbar':  os.path.join(self.icons_path, 'tools24x24.png'),
                'restart':  os.path.join(self.icons_path, 'restart24x24.png'),
                'reconnect':os.path.join(self.icons_path, 'network24x24.png'),
                'shutdown': os.path.join(self.icons_path, 'shutdown24x24.png'),}
        
        def CreatePopupMenu(self):
            menu = wx.Menu()
            icons = self.items_dict()
            create_menu_item(menu, 'show', self.on_show, icons.get('show', None))
            create_menu_item(menu, 'hide', self.on_hide, icons.get('hide', None))
            create_menu_item(menu, 'toolbar', self.on_toolbar, icons.get('toolbar', None))
            menu.AppendSeparator()
            create_menu_item(menu, 'reconnect', self.on_reconnect, icons.get('reconnect', None))
            create_menu_item(menu, 'restart', self.on_restart, icons.get('restart', None))
            create_menu_item(menu, 'shutdown', self.on_exit, icons.get('shutdown', None))
            self.menu = menu
            return menu

        def on_left_down(self, event):
            control('show')
            
        def on_show(self, event):
            control('show')
            
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
            if icon_name in self.icons.keys():
                self.current = icon_name
                self.SetIcon(self.icons.get(self.current, self.icons.values()[0]), LABEL)
                    
    class MyApp(wx.App):
        def __init__(self, icons_path):
            self.icons_path = icons_path
            wx.App.__init__(self, False)
            
        def OnInit(self):
            # print 'OnInit'
            self.trayicon = MyTaskBarIcon(self.icons_path)
            return True
        
        def OnExit(self):
            # print 'OnExit'
            self.trayicon.Destroy() 
            
        def SetIcon(self, name):
            # if self.trayicon.IsAvailable():
            self.trayicon.select_icon(name)
        
    _IconObject = MyApp(icons_path) 
    reactor.registerWxApp(_IconObject)
    # reactor.addSystemEventTrigger('after', 'shutdown', main_porcess_stopped)

# def main_porcess_stopped():
#     global _IconObject
#     print 'main_porcess_stopped', _IconObject
#    if _IconObject:
#        try:
#            _IconObject.Destroy()
#        except:
#            pass
#        del _IconObject
#        _IconObject = None

#------------------------------------------------------------------------------ 

def control(cmd):
    global _ControlFunc
    if _ControlFunc is not None:
        _ControlFunc(cmd)


def set_icon(name):
    global _IconObject
    if _IconObject is not None:
        _IconObject.SetIcon(name)
      
      
def state_changed(network, p2p):
    if network == 'DISCONNECTED':
        set_icon('gray')
        return
    if [ network, p2p, ].count('CONNECTED') == 2:
        set_icon('green')
        return
    if network == 'CONECTED' and p2p == 'DISCONNECTED':
        set_icon('red')
        return
    if [ network, p2p ].count('CONNECTED') == 1:
        set_icon('yellow')
        return
    set_icon('gray')


def SetControlFunc(f):
    global _ControlFunc
    _ControlFunc = f

#------------------------------------------------------------------------------ 

if __name__ == "__main__":
    def test_control(cmd):
        print cmd
        if cmd == 'exit':
            reactor.stop()
            print 'reactor stopped'
            # os._exit(0)
            # sys.exit()
        
    from twisted.internet import wxreactor
    wxreactor.install()
    from twisted.internet import reactor
    init(sys.argv[1])
    SetControlFunc(test_control)
    reactor.run()
    
    
    
