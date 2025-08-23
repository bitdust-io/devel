#
# Dockerfile
#
# Copyright (C) 2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (Dockerfile) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com

ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}

RUN apt-get update && apt-get install -y \
    curl openssh-server mosh nano iproute2 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install virtualenv

RUN mkdir -p /var/run/sshd \
    && echo 'AuthorizedKeysFile %h/.ssh/authorized_keys' >> /etc/ssh/sshd_config \
    && sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd \
    && sed -ri 's/^PermitRootLogin\s+.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -ri 's/UsePAM yes/#UsePAM yes/g' /etc/ssh/sshd_config

ENV COVERAGE_PROCESS_START=/app/bitdust/.coverage_config

ENV BITDUST_LOG_USE_COLORS=0
ENV BITDUST_IN_DOCKER=1

WORKDIR /app

COPY . /app/bitdust

COPY ./regress/.coverage_config /app/bitdust/
COPY ./regress/bitdust.py /app/bitdust/

# RUN find /app/bitdust -type f -name "*.py" -exec sed -i -e 's/_Debug = True/_Debug = False/g' {} +

RUN python /app/bitdust/bitdust.py install

RUN echo '#!/bin/sh\n /root/.bitdust/venv/bin/python /app/bitdust/bitdust.py "$@"' > /bin/bitdust

RUN chmod +x /bin/bitdust

RUN /root/.bitdust/venv/bin/pip install "coverage<5" coverage-enable-subprocess

RUN echo 'import coverage; coverage.process_startup();' > /app/bitdust/sitecustomize.py

ADD ./regress/ssh /app/ssh

EXPOSE 22

CMD /app/ssh/sshd.sh
