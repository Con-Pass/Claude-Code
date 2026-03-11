#FROM node:15-alpine AS js-builder
#
#ARG PROJECT_ROOT=/app
#
#COPY ./package.json ${PROJECT_ROOT}/package.json
#COPY ./yarn.lock ${PROJECT_ROOT}/yarn.lock
#
#WORKDIR ${PROJECT_ROOT}
#
#RUN yarn install --pure-lockfile
#COPY ./public/ ${PROJECT_ROOT}/public/
#COPY ./resources/ ${PROJECT_ROOT}/resources/
#
#COPY ./babel.config.js ${PROJECT_ROOT}/babel.config.js
#COPY ./.eslintignore ${PROJECT_ROOT}/.eslintignore
#COPY ./.eslintrc.js ${PROJECT_ROOT}/.eslintrc.js
#COPY ./tsconfig.json ${PROJECT_ROOT}/tsconfig.json
#COPY ./vue.config.js ${PROJECT_ROOT}/vue.config.js
#
# RUN yarn build

FROM python:3.9-slim-bullseye as django-static

ARG PROJECT_ROOT=/app
RUN \
    apt-get update && \
    buildDeps="make gcc g++ libc-dev python3-dev default-libmysqlclient-dev build-essential pkg-config" && \
    apt-get install -y --no-install-recommends $buildDeps  libxml2-dev libxmlsec1-dev libxmlsec1-openssl

RUN pip install pipenv

WORKDIR ${PROJECT_ROOT}
COPY Pipfile Pipfile.lock ${PROJECT_ROOT}/
RUN pipenv install --system --deploy
COPY . ${PROJECT_ROOT}/
RUN mkdir -p /app/logs && DJANGO_SECRET_KEY=build-placeholder DJANGO_SETTINGS_MODULE=config.settings.local python app/manage.py collectstatic --noinput

FROM nginx:1.25 AS web

ARG UID=1000
ARG GID=1000
ARG PROJECT_ROOT=/app
ARG WEB_USER=web_user

RUN apt update \
  && apt install -y locales \
  && locale-gen ja_JP.UTF-8 \
  && localedef -f UTF-8 -i ja_JP ja_JP.UTF-8 \
  && apt autoremove -y \
  && apt clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN groupadd -g ${GID} ${WEB_USER}
RUN useradd -m -u ${UID} -g ${GID} -s /bin/bash ${WEB_USER}

COPY ./docker/web/etc/nginx/conf.d/default.conf.template /etc/nginx/conf.d/default.conf.template
COPY ./docker/web/etc/nginx/nginx.conf /etc/nginx/nginx.conf
# COPY --chown=${UID}:${GID} --from=js-builder ${PROJECT_ROOT}/dist ${PROJECT_ROOT}/public
COPY --chown=${UID}:${GID} --from=django-static ${PROJECT_ROOT}/app/staticfiles ${PROJECT_ROOT}/public/static

ARG APP_HOST
ARG APP_PORT
ARG VUE_CLI_HOST
ARG VUE_CLI_PORT
RUN envsubst '$$PROJECT_ROOT $$APP_HOST $$APP_PORT $$VUE_CLI_HOST $$VUE_CLI_PORT'< /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

WORKDIR ${PROJECT_ROOT}
