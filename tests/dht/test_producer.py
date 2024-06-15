import os
import time
import optparse

from twisted.internet import reactor
from twisted.internet.defer import DeferredList

from bitdust.logs import lg
from bitdust.main import settings
from bitdust.dht import dht_service

parser = optparse.OptionParser()
parser.add_option('-s', '--start', dest='start', type='int', help='start position', default=1)
parser.add_option('-e', '--end', dest='end', type='int', help='end position', default=3)
parser.add_option('-l', '--layer', dest='layer', type='int', help='layer number', default=0)
(options, args) = parser.parse_args()


def connected(nodes, seeds=[]):
    print('connected:', nodes, seeds)
    if options.layer != 0:
        dht_service.connect(seeds, layer_id=options.layer).addBoth(layer_connected)
    else:
        run()


def layer_connected(nodes):
    print('layer_connected:', options.layer, nodes)
    run()


def run():
    print('run')

    def callback(*args, **kwargs):
        print('callback', args, kwargs)
        l = args[0]
        assert len(l) > 0

    def errback(*args, **kwargs):
        import traceback
        traceback.print_exc()

    def callback_dfl(*args):
        print('callback_dfl', args)
        reactor.stop()  # @UndefinedVariable

    errback_dfl = errback
    time.sleep(3)

    try:
        list_of_deffered_set_value = []
        for i in range(options.start, options.end + 1):
            j = {
                'key' + str(i): 'value' + str(i),
            }
            d = dht_service.set_json_value(str(i), json_data=j, age=60 * 60, layer_id=options.layer)
            d.addBoth(callback, j)
            d.addErrback(errback)
            list_of_deffered_set_value.append(d)

        dfl = DeferredList(list_of_deffered_set_value)
        dfl.addCallback(callback_dfl)
        dfl.addErrback(errback_dfl)

    except Exception as exc:
        print('ERROR in run()', exc)
        reactor.stop()  # @UndefinedVariable


def main():
    settings.init()
    lg.set_debug_level(12)
    connect_layers = []
    if options.layer != 0:
        connect_layers.append(options.layer)
    dht_service.init(udp_port=14441, open_layers=connect_layers)
    seeds = []

    for seed_env in os.environ.get('DHT_SEEDS').split(','):
        seed = seed_env.split(':')
        seeds.append((seed[0], int(seed[1])))

    print('seeds:', seeds)

    dht_service.connect(seeds).addBoth(connected, seeds=seeds)
    reactor.run()  # @UndefinedVariable
    settings.shutdown()


if __name__ == '__main__':
    main()
