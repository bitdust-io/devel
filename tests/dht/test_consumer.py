import os
import time
import argparse

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from logs import lg
from main import settings
from dht import dht_service


parser = argparse.ArgumentParser(description="Fetch records from DHT")
parser.add_argument("start", type=int, help="start number", default=1)
parser.add_argument("end", type=int, help="end number", default=10)
args = parser.parse_args()


def run(nodes):
    def callback(*args, **kwargs):
        print('callback', args)
        d = args[0]
        assert len(d) == 1
        k, v = d.popitem()
        assert k.replace('key', '') == v.replace('value', '')

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
            d = dht_service.get_json_value(str(i))
            d.addBoth(callback)
            d.addErrback(errback)
            list_of_deffered_set_value.append(d)

        dfl = DeferredList(list_of_deffered_set_value)
        dfl.addCallback(callback_dfl)
        dfl.addErrback(errback_dfl)

    except Exception as exc:
        print('ERRRORO!!', exc)
        reactor.stop()


def main():
    settings.init()

    lg.set_debug_level(12)

    dht_service.init(udp_port=14441, db_file_path=settings.DHTDBFile())

    seeds = []

    for seed_env in (os.environ.get('DHT_SEED_1'), os.environ.get('DHT_SEED_2')):
        seed = seed_env.split(':')
        seeds.append((seed[0], int(seed[1])))

    dht_service.connect(seeds).addBoth(run)
    reactor.run()


if __name__ == '__main__':
    main()
