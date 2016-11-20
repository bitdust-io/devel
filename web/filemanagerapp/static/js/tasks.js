(function(angular) {
    "use strict";
    angular.module('FileManagerApp').service('ActiveTasks', [
        '$http', 'fileManagerConfig', '$cookies',  
        function ($http, fileManagerConfig, $cookies) {

        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

        var ActiveTasks = function() {
            this.tasksList = [];
            this.packetsList = [];
            this.connectionsList = [];
            this.streamsList = [];
            this.refreshTask = null;
        };
        
        ActiveTasks.prototype.refresh = function(success, error) {
        	var self = this;
        	self.do_request('tasks', fileManagerConfig.tasksUrl, self.tasksList, success, error);
        	self.do_request('packets', fileManagerConfig.transfersUrl, self.packetsList, success, error);
        	self.do_request('connections', fileManagerConfig.connectionsUrl, self.connectionsList, success, error);
        	self.do_request('streams', fileManagerConfig.streamsUrl, self.streamsList, success, error);
        	if (self.hasTasks() || self.hasStreams() || self.hasPackets()) {
	        	if (self.refreshTask) {
	        		clearTimeout(self.refreshTask);
	        	}
	        	var duration = 500;
	        	if (self.hasStreams()) duration = 100;
	        	self.refreshTask = setTimeout(function(){ self.refresh(); }, duration);
        	}
        };        

        ActiveTasks.prototype.do_request = function(mode, url, target, success, error) {
            var self = this;
            var data = { params: {
                mode: mode,
            }};
            self.error = '';
            $http.post(url, data).success(function(data) {
            	angular.copy(data.result, target);
            	// debug.log(mode, data.result);
                if (data.error) {
                    self.error = data.error;
                    return typeof error === 'function' && error(data);
                }
                typeof success === 'function' && success(data);
            }).error(function(data) {
                typeof error === 'function' && error(data);
            });
        };        

        ActiveTasks.prototype.hasTasks = function() {
        	if (!this.tasksList) return false; 
        	return this.tasksList.length > 0;
        };

        ActiveTasks.prototype.hasPackets = function() {
        	if (!this.packetsList) return false; 
        	return this.packetsList.length > 0;
        };

        ActiveTasks.prototype.hasStreams = function() {
        	if (!this.streamsList) return false; 
        	return this.streamsList.length > 0;
        };

        ActiveTasks.prototype.hasActivity = function() {
        	if (!this.tasksList) return false; 
        	if (!this.packetsList) return false; 
        	if (!this.connectionsList) return false; 
        	if (!this.streamsList) return false; 
        	return this.tasksList.length + this.packetsList.length + this.connectionsList.length + this.streamsList.length > 0;
        };
        
        return ActiveTasks;
        
    }]);
})(angular);