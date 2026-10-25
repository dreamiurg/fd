#!/usr/bin/env bash
set -euo pipefail
# The host retains its instance role; containers must never reach IMDS.
iptables -C DOCKER-USER -d 169.254.169.254/32 -j REJECT 2>/dev/null ||
  iptables -I DOCKER-USER 1 -d 169.254.169.254/32 -j REJECT
