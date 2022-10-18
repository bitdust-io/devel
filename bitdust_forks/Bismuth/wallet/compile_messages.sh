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
po_file="${locale_dir}/${domain}.po"
mo_file="${locale_dir}/${domain}.mo"
# create .mo file from .po
msgfmt ${po_file} --output-file=${mo_file}
