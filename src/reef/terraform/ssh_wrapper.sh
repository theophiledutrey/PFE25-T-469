#!/bin/bash
# SSH wrapper using sshpass for password authentication
export SSHPASS='master'
exec sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=yes -o PubkeyAuthentication=no "$@"
