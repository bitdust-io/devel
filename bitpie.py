#!/usr/bin/python
#
# <<<COPYRIGHT>>>
#
#
#
#

import os

def main():
    try:
        os.chdir(os.path.dirname(__file__))
    except:
        pass
    import p2p.bpmain
    ret = p2p.bpmain.main()
    os._exit(ret)

if __name__ == "__main__":
    main()

