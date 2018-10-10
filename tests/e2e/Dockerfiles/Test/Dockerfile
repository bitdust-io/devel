FROM python:2.7.15

RUN apt-get update && apt-get install -yq curl && apt-get clean
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app

ADD tests /app/tests

ENTRYPOINT ["sleep", "infinity"]
