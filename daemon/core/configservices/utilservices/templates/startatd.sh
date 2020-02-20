#!/bin/sh
echo 00001 > /var/spool/cron/atjobs/.SEQ
chown -R daemon /var/spool/cron/*
chmod -R 700 /var/spool/cron/*
atd
