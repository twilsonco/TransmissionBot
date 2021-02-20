FROM python:3.8-alpine
SHELL ["/bin/sh", "-c"]

ARG USER=transmissionbot
ARG GROUP=transmissionbot
ARG INSTALLDIR=transmissionbot

RUN apk update && apk upgrade && apk add --no-cache \
  bash \
  gcc \
  musl-dev \
  linux-headers \
  zeromq-dev

RUN pip install --upgrade pip \
  && pip install --no-cache-dir \
  transmissionrpc \
  pytz \
  netifaces \
  discord.py

RUN addgroup -S $GROUP \
  && adduser \
  --disabled-password \
  --ingroup $GROUP \
  $USER \
  && mkdir $INSTALLDIR

COPY ./bot.py ./$INSTALLDIR

WORKDIR $INSTALLDIR

RUN sed -i "41s/.*/CONFIG = 'config.json'/" ./bot.py \
  && chown -R $USER:$GROUP .

USER $USER

CMD [ "python3", "./bot.py" ]