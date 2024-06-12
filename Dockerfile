FROM python:3.11-alpine

# set version label
ARG BUILD_DATE
ARG VERSION
ARG AC2MQTT_VERSION
LABEL build_version="Version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="wjbeckett"

# set python to use utf-8 rather than ascii
ENV PYTHONIOENCODING="UTF-8"

RUN \
 echo "**** install packages ****" && \
  apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers \
    && apk add libffi-dev && \
   apk add --no-cache \
        jq && \
 echo "**** install pip packages ****" && \
 echo "**** Install app ****" && \
 mkdir -p /app/ac2mqtt && \
 echo "Created App folder in /app/ac2mqtt" && \
 mkdir -p /config && \
 echo "Created config folder in /config"

# copy local files
COPY requirements.txt /app/ac2mqtt/

RUN echo "cython<3" > /tmp/constraint.txt
RUN PIP_CONSTRAINT=/tmp/constraint.txt pip install -r /app/ac2mqtt/requirements.txt

COPY monitor.py /app/ac2mqtt/
COPY README.md /app/ac2mqtt/
COPY settings/config.yml /config/config.yml
COPY broadlink_ac_mqtt/ /app/ac2mqtt/broadlink_ac_mqtt/

RUN mkdir /app/ac2mqtt/log


# ports and volumes
VOLUME /config

CMD ["python", "/app/ac2mqtt/monitor.py", "-c", "/config/config.yml"]