FROM bitdust/base

RUN bitdust set services/customer/enabled false
RUN bitdust set services/supplier/enabled false
RUN bitdust set services/proxy-transport/enabled false
RUN bitdust set services/private-messages/enabled false
RUN bitdust set services/nodes-lookup/enabled false
RUN bitdust set services/identity-propagate/enabled false

RUN bitdust set services/identity-server/host is
RUN bitdust set services/identity-server/enabled true

ENTRYPOINT ["bitdust"]
