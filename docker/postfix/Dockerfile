FROM debian:bookworm-slim

# Preseed debconf so the postfix package install doesn't try to prompt for
# its interactive "General type of mail configuration" wizard -- main.cf is
# supplied below instead, wholesale.
RUN echo "postfix postfix/main_mailer_type select No configuration" | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postfix \
    && rm -rf /var/lib/apt/lists/*

COPY main.cf /etc/postfix/main.cf
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Debian's default master.cf chroots most services (5th column) into
# /var/spool/postfix/ -- which has no /etc/resolv.conf of its own, so the
# chrooted outbound smtp delivery agent can't resolve any MX record at all
# ("Host not found, try again" on every destination). No security benefit to
# the chroot in an already Docker-isolated container, so just turn it off.
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && echo "buscomipana.com" > /etc/mailname \
    && newaliases \
    && sed -i -E 's/^(\S+\s+\S+\s+\S+\s+\S+\s+)y(\s)/\1n\2/' /etc/postfix/master.cf

EXPOSE 25

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
