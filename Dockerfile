#
# Dockerfile
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
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


FROM ubuntu:16.04

RUN apt-get update && apt-get install -y curl openssh-server mosh nano git python-dev python-pip
RUN rm -rf /var/lib/apt/lists/*
RUN pip install virtualenv

RUN mkdir /var/run/sshd
RUN echo 'root:bitdust' | chpasswd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile


ENV COVERAGE_PROCESS_START=/app/bitdust/.coverage_config

ENV BITDUST_LOG_USE_COLORS=0
ENV BITDUST_IN_DOCKER=1

WORKDIR /app

COPY . /app/bitdust

COPY ./regress/.coverage_config /app/bitdust/
COPY ./regress/bitdust.py /app/bitdust/


# Uncomment to hide all logs in the output
# RUN find /app/bitdust -type f -name "*.py" -exec sed -i -e 's/_Debug = True/_Debug = False/g' {} +

RUN python /app/bitdust/bitdust.py install

RUN echo '#!/bin/sh\n /root/.bitdust/venv/bin/python /app/bitdust/bitdust.py "$@"' > /bin/bitdust

RUN chmod +x /bin/bitdust

RUN /root/.bitdust/venv/bin/pip install "coverage<5" coverage-enable-subprocess

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
