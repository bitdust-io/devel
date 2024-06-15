#!/bin/bash


mkdir -p $HOME/.ssh/
chmod 700 $HOME/.ssh/


id_rsa=$HOME/.ssh/id_rsa
id_rsa_pub=$HOME/.ssh/id_rsa.pub


cp /app/ssh/id_rsa $id_rsa
chmod 600 $id_rsa


cp /app/ssh/id_rsa.pub $id_rsa_pub
chmod 600 $id_rsa_pub


echo "Configured SSH client: id_rsa=$id_rsa   id_rsa.pub=$id_rsa_pub"
/bin/sh -c "trap : TERM INT; (while true; do sleep 1000; done) & wait"
