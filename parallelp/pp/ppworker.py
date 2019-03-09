#!/usr/bin/env python
# ppworker.py
#
# Parallel Python Software: http://www.parallelpython.com
# Copyright (c) 2005-2009, Vitalii Vanovschi
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the author nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
"""
Parallel Python Software, PP Worker.

http://www.parallelpython.com - updates, documentation, examples and support
forums
"""

from __future__ import absolute_import
from __future__ import print_function
import six
from io import BytesIO

copyright = "Copyright (c) 2005-2009 Vitalii Vanovschi. All rights reserved"
version = "1.5.7"

_Debug = False

import sys
import os
import json
import traceback

from . import pptransport


def import_module(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def preprocess(msg):
    try:
        fname, fsources, imports = json.loads(msg)['v']
        fobjs = [compile(fsource, '<string>', 'exec') for fsource in fsources]
        for module in imports:
            try:
                globals()[module.split('.')[0]] = __import__(module)
            except:
                if _Debug:
                    open('/tmp/raid.log', 'a').write(u'%s\n' % traceback.format_exc())
                # print("An error has occured during the module import")
                sys.excepthook(*sys.exc_info())
        return fname, fobjs
    except Exception as exc:
        if _Debug:
            open('/tmp/raid.log', 'a').write(u'%s\n%s\n' % (traceback.format_exc(), msg))            


class _WorkerProcess(object):

    def __init__(self):
        self.hashmap = {}
        self.e = sys.__stderr__
        self.sout = BytesIO()
        origsout = sys.stdout
        sys.stdout = self.sout
        sys.stderr = self.sout
        sin = sys.stdin
        self.t = pptransport.PipeTransport(sin, origsout)
        self.t.send(six.text_type(os.getpid()))

    def run(self):
        try:
            # execution cycle
            while True:

                __fname, __fobjs = self.t.receive(preprocess)

                __sargs = self.t.receive()

                for __fobj in __fobjs:
                    try:
                        eval(__fobj)
                        globals().update(locals())
                    except:
                        # print("An error has occured during the " + \
                        #       "function import")
                        sys.excepthook(*sys.exc_info())

                __args = json.loads(__sargs)['v']

                __f = locals()[__fname]
                try:
                    __result = __f(*__args)
                except:
                    # print("An error has occured during the function execution")
                    sys.excepthook(*sys.exc_info())
                    __result = None

                __sresult = json.dumps({'v': (__result, self.sout.getvalue().decode('latin1')), })

                self.t.send(__sresult)
                self.sout.truncate(0)
        except:
            # print("Fatal error has occured during the function execution")
            if _Debug:
                open('/tmp/raid.log', 'a').write(u'%s\n' % traceback.format_exc())
            sys.excepthook(*sys.exc_info())
            __result = None
            __sresult = json.dumps({'v': (__result, self.sout.getvalue().decode('latin1')), })

            self.t.send(__sresult)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(__file__))
    wp = _WorkerProcess()
    wp.run()

# Parallel Python Software: http://www.parallelpython.com
