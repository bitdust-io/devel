import json
import os.path as path
from sys import exit

GENESIS_ADDRESS = 'cc846806ba14b8ec5a042d254beeeb637ee91033fa0f84c66063e0a9'


class Get:
    # "param_name":["type"] or "param_name"=["type","property_name"]
    vars = {
        'port': ['str'],
        'verify': ['bool', 'verify'],
        'testnet': ['bool'],
        'regnet': ['bool'],
        'heavy': ['bool'],
        'version': ['str', 'version'],
        'version_allow': ['list'],
        'thread_limit': ['int', 'thread_limit'],
        'rebuild_db': ['bool', 'rebuild_db'],
        'debug': ['bool', 'debug'],
        'purge': ['bool', 'purge'],
        'pause': ['int', 'pause'],
        'ledger_path': ['str', 'ledger_path'],
        'hyper_path': ['str', 'hyper_path'],
        'hyper_recompress': ['bool', 'hyper_recompress'],
        'full_ledger': ['bool', 'full_ledger'],
        'ban_threshold': ['int'],
        'tor': ['bool', 'tor'],
        'debug_level': ['str', 'debug_level'],
        'allowed': ['str', 'allowed'],
        'ram': ['bool', 'ram'],
        'node_ip': ['str', 'node_ip'],
        'light_ip': ['dict'],
        'reveal_address': ['bool'],
        'accept_peers': ['bool'],
        'banlist': ['list'],
        'whitelist': ['list'],
        'nodes_ban_reset': ['int'],
        'mempool_allowed': ['list'],
        'terminal_output': ['bool'],
        'gui_scaling': ['str'],
        'mempool_ram': ['bool'],
        'egress': ['bool'],
        'trace_db_calls': ['bool'],
        'heavy3_path': ['str'],
        'mempool_path': ['str'],
        'old_sqlite': ['bool'],
        'mandatory_message': ['list'],
    }

    # Optional default values so we don't bug if they are not in the config.
    # For compatibility
    defaults = {
        'testnet': False,
        'regnet': False,
        'heavy': True,
        'trace_db_calls': False,
        'mempool_ram': True,
        'heavy3_path': './heavy3a.bin',
        'mempool_path': './mempool.db',
        'old_sqlite': False,
        'mandatory_message': {
            'Address': 'Comment - Dict for addresses that require a message. tx to these addresses withjout a message will not be accepted by mempool.',
            'f6c0363ca1c5aa28cc584252e65a63998493ff0a5ec1bb16beda9bac': 'qTrade Exchange needs a message to route the deposit to your account',
            'd11ea307ea6de821bc28c645b1ff8dd25c6e8a9f70b3a6aeb9928754': 'VGate/ViteX Exchange needs a message to route the deposit to your account',
            '14c1b5851634f0fa8145ceea1a52cabe2443dc10350e3febf651bd3a': 'Graviex Exchange needs a message to route the deposit to your account',
            '1a174d7fdc2036e6005d93cc985424021085cc4335061307985459ce': 'Finexbox Exchange needs a message to route the deposit to your account',
            '49ca873779b36c4a503562ebf5697fca331685d79fd3deef64a46888': 'Tradesatoshi is no more listing bis but needed a message to route the deposit to your account',
            'edf2d63cdf0b6275ead22c9e6d66aa8ea31dc0ccb367fad2e7c08a25': 'Old Cryptopia address, memo',
        },  # setup here by safety, but will use the json if present for easier updates.
    }

    def load_file(self, filename):
        if not path.isfile(filename):
            filename = path.join('blockchain', 'Bismuth', filename)
        # print("Loading",filename)
        with open(filename) as fp:
            for line in fp:
                if '=' in line:
                    left, right = map(str.strip, line.rstrip('\n').split('='))
                    if 'mempool_ram_conf' == left:
                        print('Inconsistent config, param is now mempool_ram in config.txt')
                        exit()
                    if not left in self.vars:
                        # Warn for unknown param?
                        continue
                    params = self.vars[left]
                    if params[0] == 'int':
                        right = int(right)
                    elif params[0] == 'dict':
                        try:
                            right = json.loads(right)
                        except:  # compatibility
                            right = [item.strip() for item in right.split(',')]
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
        # Default genesis to keep compatibility
        self.genesis = GENESIS_ADDRESS
        for key, default in self.defaults.items():
            if key not in self.__dict__:
                setattr(self, key, default)

        # print(self.__dict__)

    def read(self, filename='config.txt', custom_filename='config_custom.txt'):
        # first of all, load from default config so we have all needed params
        self.load_file(filename)
        # then override with optional custom config
        if path.exists(custom_filename):
            self.load_file(custom_filename)
        file_name = './mandatory_message.json'
        if path.isfile(file_name):
            try:
                with open(file_name) as fp:
                    data = json.load(fp)
                    if type(data) != dict:
                        raise RuntimeWarning('Bad file format')
                    self.mandatory_message = data
                    print('mandatory_message file loaded')
            except Exception as e:
                print('Error loading mandatory_message.json {}'.format(e))
        """
        if "regnet" in self.version:
            print("Regnet, forcing ram = False")
            self.ram = False
        """
