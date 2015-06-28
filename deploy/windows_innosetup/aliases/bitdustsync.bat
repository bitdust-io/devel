@echo off 

cd ..\src

echo Running command "git clean" 
..\git\bin\git.exe clean -d -fx "" 1>NUL 

echo Running command "git reset" 
..\git\bin\git.exe reset --hard origin/master 

echo Running command "git pull" 
..\git\bin\git.exe pull 
