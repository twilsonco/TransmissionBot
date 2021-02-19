FROM python:3.8-alpine
SHELL ["/bin/sh", "-c"]

RUN apk update && apk upgrade && \
    apk add --no-cache bash git gcc musl-dev linux-headers zeromq-dev

ARG user=transmissionbot
ARG group=transmissionbot

RUN addgroup -S $group
RUN adduser \
    --disabled-password \
    --ingroup $group \
    $user

RUN git clone https://github.com/jpdsceu/TransmissionBot.git

WORKDIR TransmissionBot
RUN sed -i "41s/.*/CONFIG = 'config.json'/" ./bot.py
RUN chown -R $user:$group .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

USER $user
CMD [ "python3", "./bot.py" ]