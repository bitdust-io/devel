import sys
import os.path as _p
sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
from logs import lg
from lib import bpio
from crypt import key
from crypt import signed
from lib import settings
from lib import misc

bpio.init()
lg.set_debug_level(18)
settings.init()
key.InitMyKey()
p1 = signed.Packet('Data', misc.getLocalID(), misc.getLocalID(), 'SomeID', 'SomePayload123456', 'RemoteID:abc')
src1 = p1.Serialize()
print p1, len(src1)
p2 = signed.Unserialize(src1)
src2 = p2.Serialize()
print p2, len(src2)
print len(p1.Payload), len(p2.Payload)
print src2.count(src1)
    
    