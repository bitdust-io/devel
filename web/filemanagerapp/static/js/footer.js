(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp')
	.controller('FileManagerFooterCtrl', [
    '$scope', '$rootScope', '$http', 'fileManagerConfig',   
    function($scope, $rootScope, $http, fileManagerConfig) {

        $scope.config = fileManagerConfig;
        $scope.appName = fileManagerConfig.appName;

        $scope.initialized = function() {
        	return fileManagerConfig.stats && fileManagerConfig.stats['timestamp'];
        };
                
        $scope.suppliersInfo = function() {
        	return "suppliers: " + fileManagerConfig.stats.suppliers + "/" + 4 + " of " +fileManagerConfig.stats.max_suppliers+ " total";
        };
        
    }]);
})(window, angular, jQuery);
        