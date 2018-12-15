ARG  PYTHON_VERSION=2.7.15

FROM python:${PYTHON_VERSION}



RUN apt-get update && apt-get install -y \
    curl openssh-server mosh \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/run/sshd \
    && echo 'AuthorizedKeysFile %h/.ssh/authorized_keys' >> /etc/ssh/sshd_config \
    && sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd \
    && sed -ri 's/^PermitRootLogin\s+.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -ri 's/UsePAM yes/#UsePAM yes/g' /etc/ssh/sshd_config



WORKDIR /app

COPY . /app/bitdust

RUN python /app/bitdust/bitdust.py install

RUN echo '#!/bin/sh\n /root/.bitdust/venv/bin/python /app/bitdust/bitdust.py "$@"' > /bin/bitdust

RUN chmod +x /bin/bitdust



RUN echo 'docker' > /root/.bitdust/networkname



ADD ./regression/ssh/ /app/ssh

EXPOSE 22

CMD /app/ssh/sshd.sh
