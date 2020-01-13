FROM bitdust_perf/app

ENV dht_seeds='seed1:14441,seed2:14441,seed3:14441,seed4:14441'

ENV delayed='0'

ENV attach_layer=''

ENV join_layer=''

ENTRYPOINT /root/.bitdust/venv/bin/python /app/bitdust/dht/dht_service.py --seeds="$dht_seeds" --wait="$delayed" --layers="1,2,3" --attach_layer="$attach_layer" --join_layer="$join_layer"
