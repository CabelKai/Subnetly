FROM postgres:16-alpine

RUN apk add --no-cache bash dcron tini

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

# crontab: daily at 02:30
RUN echo "30 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1" > /etc/crontabs/root

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["crond", "-f", "-d", "8"]
