FROM bitdust/base

COPY ./tests/e2e/Dockerfiles/customer_1/file.txt /customer_1/file_customer_1.txt

#: it allow us to use api interface externally
ENV BITDUST_API_PASS_EXTERNAL_CONNECTIONS=1
ENV BITDUST_GIT_SYNC_SKIP=1

RUN bitdust set services/identity-propagate/known-servers is:8084:6661
RUN bitdust set services/entangled-dht/known-nodes "dht_seed_1:14441, dht_seed_2:14441"
RUN bitdust set services/supplier/enabled false
RUN bitdust set services/customer/suppliers-number 2
RUN bitdust set services/proxy-transport/preferred-routers "http://is:8084/proxy_server_1.xml"

ENTRYPOINT ["bitdust"]
