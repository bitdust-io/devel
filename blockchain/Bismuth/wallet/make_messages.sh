#!/usr/bin/env bash
# get arguments and init variables
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <locale> [optional: <domain_name>]"
    exit 1
fi
locale=$1
domain="messages"
if [ ! -z "$2" ]; then
    domain=$2
fi
locale_dir="locale/${locale}/LC_MESSAGES"
pot_file="locale/${domain}.pot"
po_file="${locale_dir}/${domain}.po"
# create folders if not exists
mkdir -p $locale_dir

rm -rf ./.buildozer
# create .pot file
find . -iname "*.html" -o -iname "*.py" | xargs \
    xgettext --output=${pot_file} --language=Python --from-code=UTF-8 \
    --sort-by-file --keyword=_ --keyword=_:1,2 --no-wrap
# init .po file, if it doesn't exist yet
if [ ! -f $po_file ]; then
    msginit --input=${pot_file} --output-file=${po_file} --no-wrap --locale=${locale}
else
    # update .po file
    msgmerge --no-wrap --sort-by-file --output-file=${po_file} ${po_file} ${pot_file}
fi
