FROM bitdust/base

RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"

RUN bitdust set services/customer/enabled false
RUN bitdust set services/supplier/enabled false
RUN bitdust set services/proxy-transport/enabled false
RUN bitdust set services/private-messages/enabled false
RUN bitdust set services/nodes-lookup/enabled false
RUN bitdust set services/identity-propagate/enabled false

ENTRYPOINT ["bitdust"]
