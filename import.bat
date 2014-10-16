SET curpath=%cd%
git pull
cd %1
git checkout-index -a -f --prefix="%curpath%//"
cd "%curpath%"
git status