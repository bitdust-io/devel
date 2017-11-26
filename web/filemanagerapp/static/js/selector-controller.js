(function(angular, $) {
    "use strict";
    angular.module('FileManagerApp').controller('ModalFileManagerCtrl', [
        '$scope', '$rootScope', 'fileManagerConfig', 'fileNavigator',
        function($scope, $rootScope, fileManagerConfig, FileNavigator) {

        $scope.appName = fileManagerConfig.appName;
        $scope.orderProp = ['model.type', 'model.name'];
        $scope.fileNavigator = new FileNavigator();

        $rootScope.select = function(item, temp) {
            temp.tempModel.path = item.model.fullPath().split('/');
            $('#selector').modal('hide');
        };

        $rootScope.openNavigator = function(item) {
            $scope.fileNavigator.currentPath = item.model.path.slice();
            $scope.fileNavigator.refresh();
            $('#selector').modal('show');
        };

    }]);
})(angular, jQuery);


(function(angular, $) {
    "use strict";
    angular.module('FileManagerApp').controller('ModalUploadFromFileManagerCtrl', [
        '$scope', '$rootScope', 'fileManagerConfig', 'fileNavigator',
        function($scope, $rootScope, fileManagerConfig, FileNavigator) {

        $scope.appName = fileManagerConfig.appName;
        $scope.orderProp = ['model.type', 'model.name'];
        $scope.fileNavigator = new FileNavigator();

        $rootScope.openUploadFromNavigator = function(temp) {
            $scope.fileNavigator.mode = 'select_upload_path';
            //$scope.fileNavigator.currentPath = []; // temp.tempModel.path.slice(); // item.model.path.slice();
            $scope.fileNavigator.currentPath = fileManagerConfig.localConfig['homepath'].split('/');
            //debug.log('openUploadFromNavigator', $scope.fileNavigator.currentPath);
            $scope.fileNavigator.refresh();
            $('#localselector').modal('show');
        };

    }]);
})(angular, jQuery);


(function(angular, $) {
    "use strict";
    angular.module('FileManagerApp').controller('ModalDownloadToFileManagerCtrl', [
        '$scope', '$rootScope', 'fileManagerConfig', 'fileNavigator',
        function($scope, $rootScope, fileManagerConfig, FileNavigator) {

        $scope.appName = fileManagerConfig.appName;
        $scope.orderProp = ['model.type', 'model.name'];
        $scope.fileNavigator = new FileNavigator();

        $rootScope.openDownloadToNavigator = function(temp) {
        	//debug.log('openDownloadToNavigator', temp);
            $scope.fileNavigator.mode = 'select_download_path';
            $scope.fileNavigator.targetItem = temp;
            $scope.fileNavigator.currentPath = temp.tempModel.path.slice(); // item.model.path.slice();
            $scope.fileNavigator.refresh();
            $('#downloadselector').modal('show');
        };

    }]);
})(angular, jQuery);


