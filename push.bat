@echo off
git add -u -v :/
git status
pause 
rem git commit -m "%Date:~% at %Time:~0,8%"
git commit 
git push origin
git push github