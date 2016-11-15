(function(angular) {
    "use strict";
    angular.module('FileManagerApp').service('ActiveTasks', [
        '$http', 'fileManagerConfig', '$cookies',  
        function ($http, fileManagerConfig, $cookies) {

        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

        var ActiveTasks = function() {
            this.requesting = false;
            this.requesting_transfers = false;
            this.tasksList = [];
            this.transfersList = [];
        };
        
        ActiveTasks.prototype.refresh = function(success, error) {
            return;
            var self = this;
            var data = { params: {
                mode: 'tasks',
            }};
            self.requesting = true;
            self.error = '';
            $http.post(fileManagerConfig.tasksUrl, data).success(function(data) {
                self.tasksList = [];
                angular.forEach(data.result, function(itm) {
                    self.tasksList.push(itm);
                });
                self.requesting = false;
                if (data.error) {
                    self.error = data.error;
                    return typeof error === 'function' && error(data);
                }
                typeof success === 'function' && success(data);
            }).error(function(data) {
                self.requesting = false;
                typeof error === 'function' && error(data);
            });
        };        

        ActiveTasks.prototype.refresh_transfers = function(success, error) {
            var self = this;
            var data = { params: {
                mode: 'transfers',
            }};
            self.requesting_transfers = true;
            self.error = '';
            $http.post(fileManagerConfig.transfersUrl, data).success(function(data) {
                self.transfersList = [];
                angular.forEach(data.result, function(itm) {
                    self.transfersList.push(itm);
                });
                self.requesting_transfers = false;
                if (data.error) {
                    self.error = data.error;
                    return typeof error === 'function' && error(data);
                }
                typeof success === 'function' && success(data);
            }).error(function(data) {
                self.requesting_transfers = false;
                typeof error === 'function' && error(data);
            });
        };        

        ActiveTasks.prototype.hasTasks = function() {
        	// TODO
        	// return false;
        	return this.tasksList.length + this.transfersList.length > 0;
        };
        
        return ActiveTasks;
        
    }]);
})(angular);