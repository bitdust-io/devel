#
# Dockerfile.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (Dockerfile.py) is part of BitDust Software.
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

FROM python:3.6

RUN apt-get update -y && apt-get install -y mosh openssh-client curl && rm -rf /var/lib/apt/lists/*

COPY ./regression/requirements-test.txt /requirements-test.txt

RUN pip install -r /requirements-test.txt

WORKDIR /app

ADD ./regression/tests/ /app/tests

ADD ./regression/ssh/ /app/ssh

CMD /app/ssh/sshcli.sh
