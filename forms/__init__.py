
import wx
import urllib

__SENTINEL = object()

def GetParam(tag, param, default=__SENTINEL):
    """
    Convenience function for accessing tag parameters.
    """
    if tag.HasParam(param):
        return tag.GetParam(param)
    else:
        if default == __SENTINEL:
            raise KeyError
        else:
            return default

def UnpackParam(s, default=None):
    if s is None or s == '':
        if default is not None:
            return default
        return s
    try:
        return urllib.unquote(str(s))
    except:
        return default
    
#------------------------------------------------------------------------------ 

try:
    import forms.form as form
    import forms.input as input
except:
    pass

#------------------------------------------------------------------------------ 

if __name__ == '__main__':
    app = wx.App(False)
    f = wx.Frame(None)

    html = wx.html.HtmlWindow(f, style= wx.html.HW_DEFAULT_STYLE | wx.TAB_TRAVERSAL)
    html.LoadFile(r"C:\htmlt.html")

    def OnFormSubmit(evt):
        print "Submitting to %s via %s with args %s"% (evt.form.action, evt.form.method, evt.args)
    html.Bind(form.EVT_FORM_SUBMIT, OnFormSubmit)
    f.Show()
    app.MainLoop()