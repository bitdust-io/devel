#!/usr/bin/env python
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
    import main.bpmain
    ret = main.bpmain.main()
    os._exit(ret)

if __name__ == "__main__":
    main()

