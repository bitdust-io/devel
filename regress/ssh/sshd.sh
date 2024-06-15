#!/bin/bash


mkdir -p $HOME/.ssh/
chmod 700 $HOME/.ssh/


authorized_keys=$HOME/.ssh/authorized_keys


cp /app/ssh/authorized_keys $authorized_keys
chmod 600 $authorized_keys


echo "Starting SSH daemon! authorized_keys=$authorized_keys"
/usr/sbin/sshd -D
