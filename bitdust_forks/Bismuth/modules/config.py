import sys
import os.path as path

__version__ = '0.0.5'

GENESIS_ADDRESS = 'cc846806ba14b8ec5a042d254beeeb637ee91033fa0f84c66063e0a9'


class Get:

    # "param_name":["type"] or "param_name"=["type","property_name"]
    vars = {
        'port': ['str'],
        'websocket_port': ['str'],
        'node_port': ['str'],
        'max_clients': ['int'],
        'testnet': ['bool'],
        'debug': ['bool'],
        'node_path': ['str'],
        'db_path': ['str'],
        'mempool_path': ['str'],
        'debug_level': ['str'],
        'allowed': ['str'],
        'banlist': ['list'],
        'whitelist': ['list'],
        'direct_ledger': ['bool'],
    }

    # Optional default values so we don't bug if they are not in the config.
    # For compatibility
    defaults = {
        'port': 8150,
        'websocket_port': 8155,
        'node_port': 5658,
        'node_path': '.',
        'db_path': './static',
        'mempool_path': './mempool.db',
        'debug': False,
        'testnet': False,
        'max_clients': 50,
        'direct_ledger': True,
    }

    def load_file(self, filename):
        # print("Loading",filename)
        for line in open(filename):
            if '=' in line:
                left, right = map(str.strip, line.rstrip('\n').split('='))
                if not left in self.vars:
                    # Warn for unknown param?
                    continue
                params = self.vars[left]
                if params[0] == 'int':
                    right = int(right)
                elif params[0] == 'list':
                    right = [item.strip() for item in right.split(',')]
                elif params[0] == 'bool':
                    if right.lower() in ['false', '0', '', 'no']:
                        right = False
                    else:
                        right = True

                else:
                    # treat as "str"
                    pass
                if len(params) > 1:
                    # deal with properties that do not match the config name.
                    left = params[1]
                setattr(self, left, right)
        for key, default in self.defaults.items():
            if key not in self.__dict__:
                setattr(self, key, default)

        self.node_ip = '127.0.0.1'
        self.genesis_conf = GENESIS_ADDRESS
        # print(self.__dict__)

    def read(self, filename='config.txt', custom_filename='config_custom.txt'):
        # first of all, load from default config so we have all needed params
        self.load_file(filename)
        # then override with optional custom config
        if path.exists(custom_filename):
            self.load_file(custom_filename)
        if not self.direct_ledger:
            print('Newest versions need direct_ledger to be True')
            sys.exit()
