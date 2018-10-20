FROM python:3.6

COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app

ADD tests /app/tests

ENTRYPOINT ["sleep", "infinity"]
