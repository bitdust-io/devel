import os
import time
import argparse

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from logs import lg
from main import settings
from dht import dht_service


parser = argparse.ArgumentParser(description="Generate and place records to DHT")
parser.add_argument("start", type=int, help="start number", default=1)
parser.add_argument("end", type=int, help="end number", default=10)
args = parser.parse_args()


def run(nodes):
    def callback(*args, **kwargs):
        print('callback', args)
        l = args[0]
        assert len(l) > 0

    def errback(*args, **kwargs):
        import traceback
        traceback.print_exc()

    def callback_dfl(*args):
        print('callback_dfl', args)
        reactor.stop()

    errback_dfl = errback
    time.sleep(3)

    try:
        list_of_deffered_set_value = []
        for i in range(args.start, args.end):
            j = {'key'+str(i): 'value'+str(i), }
            d = dht_service.set_json_value(str(i), j, 60 * 60)
            d.addBoth(callback, j)
            d.addErrback(errback)
            list_of_deffered_set_value.append(d)

        dfl = DeferredList(list_of_deffered_set_value)
        dfl.addCallback(callback_dfl)
        dfl.addErrback(errback_dfl)

    except:
        print('ERRRORO!!')
        reactor.stop()


def main():

    settings.init()

    lg.set_debug_level(12)

    dht_service.init(udp_port=14441, db_file_path=settings.DHTDBFile())

    seeds = []

    for seed_env in (os.environ.get('DHT_SEED_1'), os.environ.get('DHT_SEED_2')):
        seed = seed_env.split(':')
        seeds.append((seed[0], int(seed[1])))

    print(seeds)

    dht_service.connect(seeds).addBoth(run)
    reactor.run()


if __name__ == '__main__':
    main()
