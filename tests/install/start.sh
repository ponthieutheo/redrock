#!/bin/sh
# démarre le démon Docker et cron, comme systemd le ferait sur une vraie machine
service cron start >/dev/null 2>&1 || cron
dockerd > /var/log/dockerd.log 2>&1 &
exec sleep infinity
