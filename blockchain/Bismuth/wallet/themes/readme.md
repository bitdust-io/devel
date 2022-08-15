# Themes

- One dir  = one theme
- Uses Tornado templates (see https://www.tornadoweb.org/en/stable/guide/templates.html)

## Static routes

why is this needed?

See https://www.tornadoweb.org/en/stable/web.html#tornado.web.RequestHandler.static_url  
Static route uses versioning and etags to make sure static files can be cached on client side but still refreshed if updated.

The tornado wallet uses two different static routes: a common one - global for all themes and a theme relative one. 

## Common static route

This is the place to store all the css and js that are **not** theme specific and can be used by any theme or crystal.  
jquery, jquery ui, chartjs, datatable... fall into that category

**URL:** `/common/` url

**DIR:** Points to `wallet/themes/common` dir

**Use in templates:**  
In a tornado template, use the `handler.common_url` function to generate the right include.  
For instance, here is how base.html from the material theme includes jquery:  
`<script src="{{ handler.common_url('js/core/jquery.min.js') }}"></script>`
 

### Theme static

**URL:** `/static/` url

**DIR:** Points to `wallet/themes/_selected _theme_name__` dir

This is the place to store all theme specific static ressources. css, js, images.

theme specific css fall into that category

**Use in templates:**  
In a tornado template, use the `static_url` function to generate the right include.  
For instance, here is how base.html from the material theme includes the material css:  
`<link href="{{ static_url('css/material-dashboard.css') }}" rel="stylesheet"/>`

