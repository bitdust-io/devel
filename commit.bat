@echo off
git add -u :/
git status
pause 
git commit -m "%Date:~% at %Time:~0,8%"
git push origin