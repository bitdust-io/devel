FROM python:2.7.15

COPY . bitdust
COPY /Dockerfiles/Customer_2/file.txt /volume/file_customer_2.txt

WORKDIR bitdust
RUN python bitdust.py install

ENV PATH="/root/.bitdust:${PATH}"

#: it allow us to use api interface externally
ENV BITDUST_API_PASS_EXTERNAL_CONNECTIONS=1
ENV BITDUST_GIT_SYNC_SKIP=1

RUN bitdust set services/identity-propagate/known-servers is:8084:6661
RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"
RUN bitdust set services/supplier/enabled false
RUN bitdust set services/customer/suppliers-number 2
RUN bitdust set services/proxy-transport/preferred-routers "http://is:8084/proxy_server_1.xml"

ENTRYPOINT ["bitdust"]
