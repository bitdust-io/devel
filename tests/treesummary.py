import os
import sys
import os.path as _p
sys.path.insert(0, _p.abspath(_p.join(_p.dirname(_p.abspath(sys.argv[0])), '..')))
from logs import lg
from system import bpio
from p2p import p2p_service
from main import settings
from lib import nameurl

custdir = settings.getCustomersFilesDir()
ownerdir = os.path.join(custdir, nameurl.UrlFilename('http://megafaq.ru/e_vps1004.xml'))
plaintext = p2p_service.TreeSummary(ownerdir)
print plaintext
