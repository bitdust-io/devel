#!/bin/bash


bitdust stop

rm -rf ~/.bitdsut/identityserver/alice.xml

# TODO: remember current values from:
#     bitdust get services/identity-propagate/known-servers
#     bitdust get services/identity-server/host

bitdust set services/identity-propagate/known-servers 127.0.0.1:8084:6661

bitdust set services/identity-server/host 127.0.0.1

bitdust daemon

sleep 5

curl -X POST -d '{"username": "alice"}' localhost:8180/identity/create/v1

bitdust set services/identity-propagate/known-servers ""

bitdust set services/identity-server/host ""

# TODO: restore back settings with "bitdust set"
