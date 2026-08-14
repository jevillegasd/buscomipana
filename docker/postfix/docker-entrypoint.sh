#!/bin/sh
set -e

# Postfix insists on directory/file ownership matching main.cf exactly; the
# named volume mounted over /var/spool/postfix starts out root-owned, which
# start-fg refuses to run against.
postfix set-permissions 2>/dev/null || true

exec /usr/sbin/postfix start-fg
