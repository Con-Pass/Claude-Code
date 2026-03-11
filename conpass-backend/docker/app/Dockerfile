FROM python:3.9.23-bullseye as base

ARG UID=1000
ARG GID=1000
ARG PROJECT_ROOT=/app
ARG APP_USER=app_user

RUN groupadd -g ${GID} ${APP_USER} && \
    useradd -r -u ${UID} -g ${APP_USER} ${APP_USER}


RUN \
    apt-get update && \
    buildDeps="make gcc g++ libc-dev python3-dev default-libmysqlclient-dev build-essential pkg-config fonts-ipaexfont-gothic wget supervisor poppler-utils libzbar0 pandoc" && \
    apt-get install -y --no-install-recommends $buildDeps libxml2-dev libxmlsec1-dev libxmlsec1-openssl

RUN apt-get install -y --no-install-recommends wkhtmltopdf

RUN pip install pipenv uWSGI

WORKDIR ${PROJECT_ROOT}

COPY --chown=${UID}:${GID} Pipfile Pipfile.lock ${PROJECT_ROOT}/
RUN pipenv install --system --deploy
RUN pip install --force-reinstall bayoo-docx==0.2.20
# ローカル開発用追加パッケージ（Pipfile.lockとの差分を補完）
RUN pip install pdfminer.six openai
#RUN \
#    apt-get purge -y --auto-remove \
#        -o APT::AutoRemove::RecommendsImportant=false \
#        $buildDeps && \
#    rm -rf /var/lib/apt/lists/* && \
#    rm -rf /tmp/* /var/tmp/*

COPY --chown=${UID}:${GID} . ${PROJECT_ROOT}/
COPY --chown=${UID}:${GID} ./docker/app/etc/supervisor/conf.d/celery-worker.conf /etc/supervisor/conf.d/celery-worker.conf

RUN mkdir -p /home/${APP_USER}\
    && chown ${UID}:${GID} /home/${APP_USER}

USER ${APP_USER}

EXPOSE 8000

CMD ["uwsgi", "uwsgi.ini"]
