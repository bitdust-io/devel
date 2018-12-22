FROM python:3.6

RUN apt-get update -y && apt-get install -y mosh openssh-client curl && rm -rf /var/lib/apt/lists/*

COPY ./regression/requirements-test.txt /requirements-test.txt

RUN pip install -r /requirements-test.txt

WORKDIR /app

ADD ./regression/tests/ /app/tests

ADD ./regression/ssh/ /app/ssh

CMD /app/ssh/sshcli.sh
