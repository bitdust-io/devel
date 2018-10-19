ARG  PYTHON_VERSION=2.7.15
FROM python:${PYTHON_VERSION}

RUN mkdir /root/.bitdust
RUN virtualenv -p /usr/local/bin/python /root/.bitdust/venv

COPY requirements.txt .

RUN /root/.bitdust/venv/bin/pip install --upgrade pip
RUN /root/.bitdust/venv/bin/pip install -r requirements.txt

COPY . bitdust
WORKDIR bitdust
RUN echo '#!/bin/sh\n /root/.bitdust/venv/bin/python /bitdust/bitdust.py "$@"' > /root/.bitdust/bitdust
RUN chmod +x /root/.bitdust/bitdust

ENV PATH="/root/.bitdust:${PATH}"