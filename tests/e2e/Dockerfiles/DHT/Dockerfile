ARG  PYTHON_VERSION=2.7.15
FROM python:${PYTHON_VERSION}

COPY . bitdust

WORKDIR bitdust
RUN python bitdust.py install
ENV PATH="/root/.bitdust:${PATH}"

RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"

ENTRYPOINT ["/root/.bitdust/venv/bin/python", "dht/dht_service.py"]
