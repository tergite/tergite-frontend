FROM python:3.12-alpine

WORKDIR /code

RUN apk update
RUN apk add python3-dev gcc libc-dev libffi-dev bash

# the dependencies get a layer of their own, so that a change to the code alone keeps it
COPY pyproject.toml /code/
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > requirements.txt \
  && pip install --no-cache-dir --upgrade -r requirements.txt \
  && rm requirements.txt

COPY . /code/
RUN pip install --no-cache-dir --upgrade --no-deps /code/

RUN chmod +x /code/start_mss.sh

LABEL org.opencontainers.image.licenses=APACHE-2.0
LABEL org.opencontainers.image.description="Public REST API for Quantum Computers in Chalmers University"

# ENV MSS_CONFIG_FILE=
# ENV MSS_CONFIG_JSON_STR=
# ENV PRIVATE_KEY_FILE="private-mss-key.pem"
# ENV VAULT_ADDR
# ENV VAULT_TOKEN
ENV MSS_PORT=80

ENTRYPOINT ["/code/start_mss.sh"]
