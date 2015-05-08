(function() { 

    var updater_task = null;
    var flag_url = '/repaintflag/';
    
    function read_flag() {
        debug.log('read_flag');
        $.get(flag_url, function(data) {
            // debug.log('    ', data);
            if (data == 'True') {
                location.reload(true);
            } else if (data == 'None') {
                clearTimeout(updater_task);
            } else {
                updater_task = setTimeout(read_flag, 250);
                window.stop();
            }
        }).fail(function() {
            clearTimeout(updater_task);
        });
    }

    $(document).ready(function() {
        read_flag();
    });

})();