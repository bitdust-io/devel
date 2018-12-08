FROM bitdust_perf/base

ENV dht_seed_1='dht_seed_1:14441'
ENV dht_seed_2='dht_seed_2:14441'
ENV delayed='0'

ENTRYPOINT /root/.bitdust/venv/bin/python dht/dht_service.py --seeds "$dht_seed_1, $dht_seed_2" --wait "$delayed"
