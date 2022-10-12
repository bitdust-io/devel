#!/usr/bin/env python
# tray1.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (tray1.py) is part of BitDust Software.
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
from wx import ImageFromStream, BitmapFromImage, EmptyIcon
import cStringIO
import zlib
from six.moves import range

# ================================ ICON ======================================


def getData():
    return zlib.decompress(
        'x\xda\x01\x97\x03h\xfc\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\
\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x04sBIT\x08\
\x08\x08\x08|\x08d\x88\x00\x00\x03NIDAT8\x8dm\xd2ML\x9bu\x00\xc7\xf1\xef\xf3\
<\xed\xda><\xa3@\xcb\x8a\x0cp\xac8\x15\x87\x89/ \x11\xd1d&:5&#n\xc9\\\xa2\
\xc6\xc3b\xe2\xd1y0Y2\xa3q^\xcc\xb8\x9a\xb9\xf9rQc\xc6\x0es\xa4\xd1\x91\xe98\
\xc8\x96\xb98H\xc3\x8b\xc0\xc6\x00\x91\xd2\xb2\xa7}\xda\xe7\xa5\xcf\xd3\xf6\
\xf9{0\xa2\x07\xbf\xf7_\xf29\xfc$\x00\xf1>\xb2\xd9\xc7\tI0$\xc0\xd5d\x06\xa5\
\x17q\xf9O\xa5\x0b$$\x85KB\xa2\xec\xcb\xbc\x1e}\x81\xdf\x01$q\x9a`>\xce\xc9`\
\xc7\x91#\xa1\xce\xa3;\xed\xdbg\xb3s\x19c\xe1\x9cz\xbe*A\x0f\x80\x80\xf4A\
\xeb\xb0\xfcPG\xa2;\x10\x8aI\xe5\xd9\x93\x8bB\xe6`l\x88U)\xf3-\xc7\xc3\xbb_{\
;r\xef\xe1Vci\xa4\xb0\xbc:\x17\xb8\xdczQ\xd3B5"A\x1f\x00\xa7"\xe39\x16\xfb\
\xd6_\xb1wu\x1f@\xa9\x15-k\xe6\xd4j\xa2D\xbf\xec\x95\x91\xe5PGX_\x18),.\xcei\
W\xdb\xbf\xd3:\xb7{49\x0e\xeem\x1dkAG+Z\xb4l\xdf\xc6o-\xc3\xea\x9fK\xbf\x84\
\xe5\xa6\xfe&\xa1>\xa8\xad)\xec\x96n}\xc6`E\xa8g7\x95d\xdbD\xf2\x82\xda\xae\
\x06\x08\xd95\x1e\xeej\xa2\xa1^F \xa1\x1b5\xae\xcf\xe5\xa8D\x14\xea\xf4\xf3\
\xdco\x9es\xb7\x9933\xe1Z\xe9U\t\xe0\xd8\xe7\x17?\t4\xecz7\x99\xd0hp\x05\x87\
\xf6u\x927\x0c6-\x87\xf6\xd6\x16\x00\xaa\x02\xbeN\xdd\xc2\xd7\x04\x99\xec:9K\
\xf9\xf8\xd37\x07\x8e\xcb\x00\x99\xca=\xbd\xbe\x00\xbf\xe4\xb1wO\x0c\xbb*\
\x08\x06\x83\x8c\xfd\xf8\x03E\xc3\xa0\xe2\xba\\\x1a\xfb\x99\xee=q\x8c\xac\
\x83#7RtC\x03\x00\x01\x80r\xd9\xea\xa9z2\x86\xeb\x13\x8bEpk\x82:U\xe5\x8f\
\x95\x15\xc6~\x1a\'=5\xc9\xb3\xcf\xef\xa7q\x87Jn\xd3A4\x04)\x97\xad\x1e\x00\
\x19\xc0\xb3-,\xbb\x82\xe3\xf9\xb85\xa8\xf8\x905J\xd4i\x1a\xe9\xa9I^:0\xc4#\
\xbd}\xb8U\xa8x>\x96]\xc1\xb3-\xb6\x04^\xd9N\x17K\x91gv\xc6\x03,el\xeek\x8b\
\x82\x1c\xe6\xd1\xc7\xfby\xa0g/j\xb4\x1e\xd3\x85\xd5\x8cE0"\x91+\xd9xe;\xfd\
\xaf\xc0\xb1\xae\x14\r\x03\xbd\xecr\xf5\xe6\x06\xc1\x10\xd4\x85\x83<5\xf8$\
\xf1\xc6zB\x80\x16\x86_of\xf1\xf0(\x1a\x06\x9ec]\xd9\x12\xb8\xb63\xea:\xe6\
\xa1\xd9\x9a\xd2-\xb7U\xf9bD\xf0\\o\x82\xaeD\x1d\x08X\xc9Z\x8c^\xcbP4\xd6\
\x99\xdf\xb00\xf3k3\x08e\x14@\xfa\xe7\xeb}GO\xbd\xf5Xr\xc7\xf0BAS[\xe3\x1a\
\xb1P\x08\xc5\x97\xa9\xf9\x82\x8aT\xc5\xf0\\\xaa\xd5*\xaa\xb8k\xa7\xefl\xbes\
\xfd\xcc\xb1\xd3[\x02\x80\xe17\x9e\x98\x8fF\xa3jv3_;12\xaf\xccJ*\xb2\x12\x06\
\xc0\xaf\x95iV+\xbc\xf7rR\xc8rcD\xa2kv\xe0\xcc\xdf;\x19 \x95J5\x17\n\x85\xef\
\xc3\xe10f\xa9`\x98\xf9;\x1f\xda\xb9\xe9qk\xe3\x86nm\xdc\xd0\xed\xdc\xf4\xf8\
\xf2\xf2\xfc\x07\x85B\xdel\x8e\xc7%]\xd7/\xa7R\xa9\xe4\x96\xc04M\xc7q\x9c\
\xb5\x89\x89\x89N!\xc4\xd3S\xdf|4\xcd\xfftw\xff\x97_]\xd3\xf5I\xc0\xf2}\xdf\
\x02\xf8\x0b\xc1.\x9e\xd8Y.\x85\x85\x00\x00\x00\x00IEND\xaeB`\x822\x86\xba\
\xb3',
    )


def getBitmap():
    return BitmapFromImage(getImage())


def getImage():
    stream = cStringIO.StringIO(getData())
    return ImageFromStream(stream)


def getIcon():
    icon = EmptyIcon()
    icon.CopyFromBitmap(getBitmap())
    return icon


# ============================================================================


class MainWindow(wx.Frame):

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        self.number = 0
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.panel = wx.Panel(self)
        self.button = wx.Button(self.panel, label='Test')
        self.button.Bind(wx.EVT_BUTTON, self.OnButton)
        self.tbicon = wx.TaskBarIcon()
        self.tbicon.SetIcon(getIcon(), 'Test')
        self.sizer = wx.BoxSizer()
        self.sizer.Add(self.button)
        self.panel.SetSizerAndFit(self.sizer)
        self.Show()

#   --------------------------------------------------------------------------

    def OnClose(self, e):
        self.tbicon.Destroy()
        self.Destroy()
        wx.Exit()


#   --------------------------------------------------------------------------

    def OnButton(self, e):
        # HERE WE GO!
        self.number += 1

        bitmap = getBitmap()

        # Find unused color
        image = bitmap.ConvertToImage()
        my_solid_color = wx.Color(*image.FindFirstUnusedColour(0, 0, 0)[1:])

        # Use the unused *unique* color to draw
        dc = wx.MemoryDC()
        dc.SetTextForeground(my_solid_color)
        dc.SelectObject(bitmap)
        # dc.DrawText(str(self.number), 0, 0)
        dc.SelectObject(wx.NullBitmap)

        # Convert the bitmap to Image again
        # and fix the alpha of pixels with that color
        image = bitmap.ConvertToImage()
        for x in range(image.GetWidth()):
            for y in range(image.GetHeight()):
                p = wx.Colour(image.GetRed(x, y), image.GetGreen(x, y), image.GetBlue(x, y))
                if p == my_solid_color:
                    image.SetAlpha(x, y, 255)  # Clear the alpha
                    image.SetRGB(x, y, 0, 0, 0)  # Set the color that we want

        # Convert back to Bitmap and save to Icon
        bitmap = image.ConvertToBitmap()
        icon = wx.IconFromBitmap(bitmap)
        self.tbicon.SetIcon(icon, 'Test')

app = wx.App(False)
win = MainWindow(None)
app.MainLoop()
