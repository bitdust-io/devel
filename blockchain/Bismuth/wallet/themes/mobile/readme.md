# WIP Mobile Wallet, broken as for now

# Theme organisation

This directory contains the files responsible for the look and feel of the wallet.

These are standard html/css/js files.

## Template engine

This uses the default Tornado template engine.

https://www.tornadoweb.org/en/stable/guide/templates.html

A Tornado template is just HTML (or any other text-based forFilesmat) with Python control sequences and expressions embedded within the markup

They also support template inheritance (all templates derive from base.html)

## Files

Main views are .html under the `theme` dir and should be named exactly like their matching route.

All static files (images, css, js) are to be located in a `static` dir under `theme`

a `modules` directory can be used for sub templates that could then be used in several templates.
