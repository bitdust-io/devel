ARG  PYTHON_VERSION=2.7.15
FROM python:${PYTHON_VERSION}

COPY . bitdust

WORKDIR bitdust
RUN python bitdust.py install

ENV PATH="/root/.bitdust:${PATH}"

RUN bitdust set services/identity-server/host is
ENTRYPOINT ["bitdust", "identity", "server", "start"]
