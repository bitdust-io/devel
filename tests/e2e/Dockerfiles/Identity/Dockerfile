FROM python:2.7.15

COPY . bitdust

WORKDIR bitdust
RUN python bitdust.py install

ENV PATH="/root/.bitdust:${PATH}"

RUN bitdust set services/identity-server/host is
ENTRYPOINT ["bitdust", "identity", "server", "start"]
