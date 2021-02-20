FROM python:3.8-alpine
SHELL ["/bin/sh", "-c"]

ARG user=transmissionbot
ARG group=transmissionbot
ARG installdir=transmissionbot

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

RUN addgroup -S $group \
  && adduser \
  --disabled-password \
  --ingroup $group \
  $user \
  && mkdir $installdir

COPY ./bot.py ./$installdir

WORKDIR $installdir

RUN sed -i "41s/.*/CONFIG = 'config.json'/" ./bot.py \
  && chown -R $user:$group .

USER $user

CMD [ "python3", "./bot.py" ]