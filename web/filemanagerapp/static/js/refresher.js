(function(window, angular, $) {
	
	var flag_url = '/repaintflag'; 
	var refresher_task = null;

	function read_flag() {
        // debug.log('read_flag');
        $.get(flag_url, function(data) {
            // debug.log('    ', data);
            if (data == 'True') {
            	debug.log('need to update !!!', $("html"), angular.element($("html")).scope().fileNavigator); 
                // location.reload(true);
            	angular.element($("html")).scope().fileNavigator.refresh();
            } else if (data == 'False') {
            	//debug.log('not need to update'); 
            } else if (data == 'None') {
            	debug.log('repaintflag is None, stop refreshing');
            	window.clearInterval(refresher_task);
            } else {
            	//debug.log('WARNING, wrong value: ', data);
                // updater_task = setTimeout(read_flag, 250);
                // window.stop();
            }
        }).fail(function() {
        	debug.log('FAIL, stop refreshing');
        	window.clearInterval(refresher_task);
        });
    } 
	
	var refresher_task = window.setInterval(function() {
		read_flag();
	},	
	250);
	
	debug.log('refreshing STARTED, update every 250 ms');

})(window, angular, jQuery);