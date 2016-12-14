/*!
 * Angular FileManager v1.0.1 (https://github.com/joni2back/angular-filemanager)
 * Jonas Sciangula Street <joni2back@gmail.com>
 * Licensed under MIT (https://github.com/joni2back/angular-filemanager/blob/master/LICENSE)
 */

(function(window, angular, $) {
    "use strict";
    var app = angular.module('FileManagerApp', 
    	['pascalprecht.translate', 'ngCookies']);

    app.directive('angularFileManager', ['$parse', 'fileManagerConfig', function($parse, fileManagerConfig) {
        return {
            restrict: 'EA',
            templateUrl: fileManagerConfig.tplPath + '/index.html'
        };
    }]);

    app.directive('angularFileManagerFooter', ['$parse', 'fileManagerConfig', function($parse, fileManagerConfig) {
        return {
            restrict: 'EA',
            templateUrl: fileManagerConfig.tplPath + '/footer.html'
        };
    }]);

    app.directive('angularFileManagerDebug', ['$parse', 'fileManagerConfig', function($parse, fileManagerConfig) {
        return {
            restrict: 'EA',
            templateUrl: fileManagerConfig.tplPath + '/debug.html'
        };
    }]);
    
    app.directive('ngFile', ['$parse', function($parse) {
        return {
            restrict: 'A',
            link: function(scope, element, attrs) {
                var model = $parse(attrs.ngFile);
                var modelSetter = model.assign;

                element.bind('change', function() {
                    scope.$apply(function() {
                        modelSetter(scope, element[0].files);
                    });
                });
            }
        };
    }]);

    app.directive('ngRightClick', ['$parse', function($parse) {
        return function(scope, element, attrs) {
            var fn = $parse(attrs.ngRightClick);
            element.bind('contextmenu', function(event) {
                scope.$apply(function() {
                    event.preventDefault();
                    fn(scope, {$event: event});
                });
                return false;
            });
        };
    }]);

    app.filter('strLimit', ['$filter', function($filter) {
        /*going to use css3 ellipsis instead of this*/
        return function(input, limit) {
            if (input.length <= limit) {
                return input;
            }
            return $filter('limitTo')(input, limit) + '...';
        };
    }]);

    app.filter('percentToFloat', function() {
        return function(input) {
          return parseInt(input.slice(0, -1), 10);
        };
    });

    app.filter('greenPercentGradient', function() {
        return function(input) {
        	var val = parseInt(input.slice(0, -1), 10);
        	return "linear-gradient(to right, lightgreen, lightgreen " + (val) + "% , white " + (val+10) + "% , white)";
        };
    });

    app.filter('bluePercentGradient', function() {
        return function(input) {
        	var val = parseInt(input.slice(0, -1), 10);
        	return "linear-gradient(to right, lightblue, lightblue " + (val) + "% , white " + (val+10) + "% , white)";
        };
    });

    $(window.document).on('shown.bs.modal', '.modal', function() {
        var self = this;
        var timer = setTimeout(function() {
            $('[autofocus]', self).focus();
            timer && clearTimeout(timer);
        }, 100);
    });

    
})(window, angular, jQuery);
