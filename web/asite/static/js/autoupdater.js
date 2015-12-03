
var lastupdate = 0;
var refresh_callback = null;
var updater_task = null;
var short_pool_url = '/repaintstate';
var refresh_interval = 100;  
var refresh_interval_min = 100;
var refresh_interval_max = 5000;

function readData() {
	$.ajax({
		type: 'GET',
	    dataType: 'json',
	    contentType: 'application/json; charset=utf-8',
	    url: short_pool_url,
        async: true,
        cache: false,
        timeout:refresh_interval_max,
        
        success: function(data) {
        	//debug.log('readData.response: ', data, data.length);
        	if (data['refresh']) {
            	intervalUp();
            	nextUpdate();
       		    //debug.log('REFRESHING', updater_task, refresh_interval);
            	if (refresh_callback) {
            		refresh_callback(data);
            	};
        	} else if (data['stop']) {
        		debug.log('STOP REFRESHING');
        		stopUpdater();
        		return;
            } else {
	        	intervalDown();
	        	nextUpdate();
            }
        },
        fail: function(XMLHttpRequest, textStatus, errorThrown) {
    		debug.log('REFRESHING FAILED', updater_task, refresh_interval);
        	intervalDown();
        	nextUpdate();
        }
    });	
};

function nextUpdate() {
	if (updater_task) {
		clearTimeout(updater_task);
	}
	updater_task = setTimeout('readData();', refresh_interval);
};

function intervalUp() {
	refresh_interval = refresh_interval / 2;
	if (refresh_interval < refresh_interval_min) {
		refresh_interval = refresh_interval_min
	}
};

function intervalDown() {
	refresh_interval = refresh_interval * 2;
	if (refresh_interval > refresh_interval_max) {
		refresh_interval = refresh_interval_max
		debug.log('SLOW REFRESHING');
	}
};

function startUpdater() {
	readData();
};

function stopUpdater() {
	if (updater_task) {
		clearTimeout(updater_task);
	}
    updater_task = null;
};

var setRefreshCallback = function (cb) {
	refresh_callback = cb;
};


