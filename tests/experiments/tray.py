#!/usr/bin/env python
# tray.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (tray.py) is part of BitDust Software.
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
from __future__ import absolute_import
import wx
import string

import sys
from six.moves import map
from six.moves import range

ID_ICON_TIMER = wx.NewId()

##
# The IconBar class
#


class IconBar:

    ##
    # \brief the constructor default left: red, default right: green
    #
    def __init__(self, l_off=[128, 0, 0], l_on=[255, 0, 0], r_off=[0, 128, 0], r_on=[0, 255, 0]):
        self.s_line = '\xff\xff\xff' + '\0' * 45
        self.s_border = '\xff\xff\xff\0\0\0'
        self.s_point = '\0' * 3
        self.sl_off = string.join(list(map(chr, l_off)), '') * 6
        self.sl_on = string.join(list(map(chr, l_on)), '') * 6
        self.sr_off = string.join(list(map(chr, r_off)), '') * 6
        self.sr_on = string.join(list(map(chr, r_on)), '') * 6

    ##
    # \brief gets a new icon with 0 <= l,r <= 5
    #
    def Get(self, l, r):
        s = '' + self.s_line
        for i in range(5):
            if i < (5 - l):
                sl = self.sl_off
            else:
                sl = self.sl_on

            if i < (5 - r):
                sr = self.sr_off
            else:
                sr = self.sr_on

            s += self.s_border + sl + self.s_point + sr + self.s_point
            s += self.s_border + sl + self.s_point + sr + self.s_point
            s += self.s_line

        image = wx.EmptyImage(16, 16)
        image.SetData(s)

        bmp = image.ConvertToBitmap()
        bmp.SetMask(wx.Mask(bmp, wx.BLACK))  # sets the transparency colour to white

        icon = wx.EmptyIcon()
        icon.CopyFromBitmap(bmp)

        return icon


##
# The TaskBarIcon class
#


class MyTaskBarIcon(wx.TaskBarIcon):

    l = 0
    r = 0

    ##
    # \brief the constructor
    #
    def __init__(self, frame):
        wx.TaskBarIcon.__init__(self)
        self.frame = frame
        self.IconBar = IconBar((127, 127, 0), (255, 255, 0), (0, 127, 127), (0, 255, 255))
        self.SetIconBar(self.l, self.r)

    ##
    # \brief sets the icon timer
    #
    def SetIconTimer(self):
        self.icon_timer = wx.Timer(self, ID_ICON_TIMER)
        wx.EVT_TIMER(self, ID_ICON_TIMER, self.BlinkIcon)
        self.icon_timer.Start(10000)

    ##
    # \brief blinks the icon and updates self.l and self.r
    #
    def BlinkIcon(self, event):
        self.SetIconBar(self.l, self.r)
        self.l += 1
        if self.l > 5:
            self.l = 0
            self.r += 1
            if self.r > 5:
                self.r = 0

    ##
    # \brief sets the icon bar and a message
    #

    def SetIconBar(self, l, r):
        icon = self.IconBar.Get(l, r)
        self.SetIcon(icon, 'L:%d,R:%d' % (l, r))


##
# The task bar application
#


class TaskBarApp(wx.Frame):

    ##
    # \brief the constructor
    #
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, -1, title, size=(1, 1), style=wx.FRAME_NO_TASKBAR | wx.NO_FULL_REPAINT_ON_RESIZE)

        self.tbicon = MyTaskBarIcon(self)
        self.tbicon.SetIconTimer()

        self.Show(True)


##
# The main application wx.App class
#


class MyApp(wx.App):

    def OnInit(self):
        frame = TaskBarApp(None, -1, ' ')
        frame.Center(wx.BOTH)
        frame.Show(False)
        return True


def main(argv=None):
    if argv is None:
        argv = sys.argv

    app = MyApp(0)
    app.MainLoop()


if __name__ == '__main__':
    main()
