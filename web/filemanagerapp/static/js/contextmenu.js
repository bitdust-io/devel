(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp').run( function($rootScope) {

		$rootScope.openContextMenu = function(menuselector, event) {
	    	debug.log('openContextMenu', menuselector, event.pageX - $('#filemanager').offset().left + 10, event.pageY - $('#filemanager').offset().top - 10);
	        $(".context-menu").hide();
	        $(menuselector).css({
	            left: event.pageX - $('#filemanager').offset().left + 10,
	            top: event.pageY - $('#filemanager').offset().top - 10,
	        }).show();
		};
		
	    $(window.document).on('click', function() {
	    	//debug.log('.context-menu - hide()');
	        $(".context-menu").hide();
	    });
	
/*
	
	    var itemSelectors = '.main-navigation .file-item td a, .iconset .thumbnail';
	    var activeTaskSelectors = '.active-tasks-panel .active-task';
	    var versionSelectors = '.version';
	    
	    $(window.document).on('contextmenu click', itemSelectors, function(e) {
	    	//debug.log('context-menu-item', e, $rootScope);
	        e.preventDefault();
	        $rootScope.openContextMenu('#context-menu-item', e);
			return false;
	    });
	
	    $(window.document).on('contextmenu click', activeTaskSelectors, function(e) {
	    	//debug.log('context-menu-active-task', e, $rootScope);
	        e.preventDefault();
	        $rootScope.openContextMenu('#context-menu-active-task', e);
	        return false;
	    });
	
	    $(window.document).on('contextmenu click', versionSelectors, function(e) {
	    	//debug.log('context-menu-version', e);
	        e.preventDefault();
	        $rootScope.openContextMenu('#context-menu-version', e);
	        return false;
	    });
*/
		
    });
    
})(window, angular, jQuery);
