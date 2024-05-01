WEB_ROOT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="msapplication-TileColor" content="#da532c">
    <meta name="theme-color" content="#ffffff">
    <meta property="og:image:width" content="2400">
    <meta property="og:image:height" content="1257">
    <meta property="og:title" content="%(title)s">
    <meta property="og:description"
          content="Distributed secure anonymous on-line storage, where only the owner has access and absolute control over its data.">
    <meta property="og:url" content="%(site_url)s">
    <meta property="og:image" content="%(basepath)sassets/img/og/og-image.jpg">

    <title data-content="pageTitle">%(title)s</title>

    <link rel="manifest" href="%(basepath)ssite.webmanifest"/>

    <link rel="apple-touch-icon" sizes="180x180" href="%(basepath)slogos/logo-pictogram-color.png"/>
    <link rel="icon" type="image/png" sizes="32x32" href="%(basepath)slogos/logo-pictogram-color.png"/>
    <link rel="icon" type="image/png" sizes="16x16" href="%(basepath)slogos/logo-pictogram-color.png"/>
    <link rel="mask-icon" href="%(basepath)slogos/logo-pictogram-color.svg" color="#5bbad5"/>

    <link href="https://fonts.googleapis.com/css?family=Source+Sans+Pro:600,700" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css?family=Open+Sans:600" rel="stylesheet">
    <link rel="stylesheet" href="%(basepath)sassets/css/applify.min.css" type="text/css"/>
    <link rel="stylesheet" href="%(basepath)sassets/css/tables.css" type="text/css"/>
    <link rel="stylesheet" href="%(basepath)scss/automat.css" type="text/css"/>

</head>

<body data-fade_in="on-load">

<nav class="navbar navbar-fixed-top navbar-dark bg-indigo">
    <div class="container">

        <!-- Navbar Logo -->
        <a class="ui-variable-logo navbar-brand" href="%(site_url)s/" title="BitDust">
            <!-- Default Logo -->
            <img class="logo-default" src="%(basepath)sassets/img/logo/bitdust-logo-white.svg" alt="BitDust">
            <!-- Transparent Logo -->
            <img class="logo-transparent" src="%(basepath)sassets/img/logo/bitdust-logo-white.svg" alt="BitDust">
        </a><!-- .navbar-brand -->

        <!-- Navbar Navigation -->
        <div class="ui-navigation navbar-center">
            <ul class="nav navbar-nav">
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#product">Product</a>
                </li>
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#problem">Problem</a>
                </li>
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#solution">Solution</a>
                </li>
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#ecosystem">Ecosystem</a>
                </li>
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#roadmap">Roadmap</a>
                </li>
                <!-- Nav Item -->
                <li>
                    <a href="%(site_url)s/index.html#team">Team</a>
                </li>
                <!-- Nav Item -->
                <li class="active">
                    <a href="%(wikipath)s">Wiki</a>
                </li>

                <!-- Nav Item -->
                <li class="dropdown active">
                    <a href="#" class="dropdown-toggle" data-toggle="dropdown">
                        Network
                    </a>
                    <ul class="dropdown-menu">
                        <li class="dropdown-item">
                            <a href="%(idserverspath)s" style="color:#8089ff;">ID servers</a>
                        </li>
                        <li class="dropdown-item">
                            <a href="%(blockchainpath)s" style="color:#8089ff;">Blockchain</a>
                        </li>
                    </ul>
                </li>

            </ul><!--.navbar-nav -->
        </div><!--.ui-navigation -->

        <!-- Navbar Button -->
        <a href="%(site_url)s/index.html#product"
           class="btn btn-sm ui-gradient-peach pull-right">
            Get Started
        </a>


    </div><!-- .container -->
</nav> <!-- nav -->


<!-- Main -->
<div class="%(div_main_class)s" role="main">

%(div_main_body)s

<!-- Footer -->
<footer class="ui-footer bg-gray">

    %(pre_footer)s

    <!-- Footer Copyright -->
    <div class="footer-copyright bg-dark-gray">
        <div class="container">
            <div class="row">
                <!-- Copyright -->
                <div class="col-sm-6 center-on-sm">
                    <p>
                        &copy; 2019 <a href="%(site_url)s" target="_blank" title="BitDust">BitDust</a>
                    </p>
                </div>
                <!-- Social Icons -->
                <div class="col-sm-6 text-right">
                    <ul class="footer-nav">
                        <li>
                            <a href="%(wikipath)s">
                                Wiki
                            </a>
                        </li>
                        <li>
                            <a href="https://github.com/bitdust-io/">
                                Github
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
        </div><!-- .container -->
    </div><!-- .footer-copyright -->

</footer><!-- .ui-footer -->

</div>
<!-- Main -->


<!-- Scripts -->
<script src="%(basepath)sassets/js/libs/jquery/jquery-3.2.1.min.js"></script>
<script src="%(basepath)sassets/js/libs/bootstrap.js"></script>
<script src="%(basepath)sassets/js/libs/owl.carousel/owl.carousel.min.js"></script>
<script src="%(basepath)sassets/js/libs/slider-pro/jquery.sliderPro.min.js"></script>
<script src="%(basepath)sassets/js/libs/form-validator/form-validator.min.js"></script>
<script src="%(basepath)sassets/js/applify/ui-map.js"></script>
<script src="%(basepath)sassets/js/applify/build/applify.js"></script>
%(google_analytics)s
<!-- Scripts -->

</body>
</html>"""

div_main_class = 'main wiki'

div_main_body = ''

GOOGLE_ANALITICS = """
<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=%(google_analytics_code)s"></script>
<script>
    window.dataLayer = window.dataLayer || [];

    function gtag() {
        dataLayer.push(arguments);
    }

    gtag('js', new Date());

    gtag('config', '%(google_analytics_code)s');
</script>
"""

google_analytics = GOOGLE_ANALITICS % dict(google_analytics_code='', )

pre_footer = """
<div class="container pt-6 pb-6">
    <div class="row">
        <div class="col-sm-8 footer-about footer-col center-on-sm">
            <img src="%(basepath)sassets/img/logo/bitdust-logo-white.svg" alt="BitDust" />
            <p class="mt-1">
                We are currently with a small team primarily focusing on the development and supporting the BitDust community.
                Join us via Telegram or send a email.
            </p>
        </div>

        <div class="col-md-4 col-sm-6 footer-col center-on-sm">
            <div>
                <a class="btn ui-gradient-purple btn-circle shadow-md" href="https://t.me/bitdust" target="_blank">
                    <span class="fa fa-telegram"></span>
                </a>
                <a class="btn ui-gradient-blue btn-circle shadow-md" href="https://github.com/bitdust-io/" target="_blank">
                    <span class="fa fa-github"></span>
                </a>
            </div>
        </div>
    </div><!-- .row -->
</div><!-- .container -->
"""
