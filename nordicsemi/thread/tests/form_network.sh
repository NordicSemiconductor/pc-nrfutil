#!/bin/bash

PREFIX=1234:1234:1234:1234

wpantund_pid=$(pidof wpantund)

if [ ! -z ${wpantund_pid} ]; then
	echo "Killing wpantund"
	kill ${wpantund_pid}
fi

nohup wpantund &

sleep 3

wpanctl set Network:Key --data 00112233445566778899aabbccddeeff && \
wpanctl form pisz-test && \
wpanctl set Network:PANID 1234 && \
wpanctl set Network:XPANID --data dead00beef00cafe && \
wpanctl config-gateway -d ${PREFIX}:: && \
wpanctl status

ip a add ${PREFIX}::1 dev wpan0
