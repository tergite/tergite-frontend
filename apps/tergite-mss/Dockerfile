FROM python:3.12-alpine

WORKDIR /code

COPY . /code/

RUN apk update
RUN apk add python3-dev gcc libc-dev libffi-dev bash
RUN pip install --no-cache-dir --upgrade /code/

RUN chmod +x /code/start_mss.sh

LABEL org.opencontainers.image.licenses=APACHE-2.0
LABEL org.opencontainers.image.description="Public REST API for Quantum Computers in Chalmers University"

# ENV MSS_CONFIG_FILE=
ENV MSS_PORT=80

ENTRYPOINT ["/code/start_mss.sh"]
