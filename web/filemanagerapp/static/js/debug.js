(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp')
	.controller('FileManagerDebugCtrl', [
    '$scope', '$rootScope', '$http', 'fileManagerConfig',   
    function($scope, $rootScope, $http, fileManagerConfig) {

        $scope.config = fileManagerConfig;
        $scope.appName = fileManagerConfig.appName;

        $scope.automatsList = function() {
        	// debug.log('automatsList', fileManagerConfig.debugInfo.automats);
        	// return fileManagerConfig.debugInfo.automats;
        	return [];
        };
        
    }]);
})(window, angular, jQuery);
        