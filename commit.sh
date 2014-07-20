#!/bin/bash
git add -u :/
git status
read -p "OK?"
git commit -m "`LANG=en_EN date`"
git push origin

