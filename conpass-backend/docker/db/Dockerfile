FROM mysql:5.7

ENV LC_ALL C.UTF-8

COPY ./docker/db/conf.d/ /etc/mysql/conf.d/

RUN mkdir -p /var/log/mysql && chown mysql:mysql /var/log/mysql

CMD ["mysqld"]
