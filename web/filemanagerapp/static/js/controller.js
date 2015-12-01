(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp').controller('FileManagerCtrl', [
    '$scope', '$rootScope', '$translate', '$cookies', '$interval', '$http', 
	'fileManagerConfig', 'item', 'fileNavigator', 'fileUploader', 'ActiveTasks',  
    function($scope, $rootScope, $translate, $cookies, $interval, $http, 
    		fileManagerConfig, Item, FileNavigator, FileUploader, ActiveTasks) {

        $scope.config = fileManagerConfig;
        $scope.appName = fileManagerConfig.appName;
        $scope.orderProp = ['model.type', 'model.name'];
        $scope.query = '';
        $scope.temp = new Item();
        $scope.tempVersion = null;
        $scope.fileNavigator = new FileNavigator();
        $scope.fileUploader = FileUploader;
        $scope.activeTasks = new ActiveTasks();
        $scope.uploadFileList = [];
        $scope.viewTemplate = $cookies.viewTemplate || 'main-table.html';
        $scope.refresher_task = null;
        $scope.refresh_interval = 500;

        $scope.setTemplate = function(name) {
            $scope.viewTemplate = $cookies.viewTemplate = name;
        };

        $scope.changeLanguage = function (locale) {
            if (locale) {
                return $translate.use($cookies.language = locale);
            }
            $translate.use($cookies.language || fileManagerConfig.defaultLang);
        };

        $scope.touch = function(item) {
            item = (item && item.revert && item) || new Item();
            item.revert && item.revert();
            $scope.temp = item;
        };

        $scope.smartClick = function(item, $event) {
            if (item.isFolder()) {
                return $scope.fileNavigator.folderClick(item);
            };
    		$scope.touch(item);
        	$rootScope.openContextMenu('#context-menu-item', $event);
        };

        $scope.smartRightClick = function(item, $event) {
    		$scope.touch(item);
        	$rootScope.openContextMenu('#context-menu-item', $event);
        };

        $scope.smartClickVersion = function(item, version, $event) {
    		$scope.touch(item);
            $scope.tempVersion = version;
        	$event.stopPropagation();
        	$rootScope.openContextMenu('#context-menu-version', $event);
        };

        $scope.smartRightClickVersion = function(item, version, $event) {
        	debug.log('smartRightClickVersion', item, version);
    		$scope.touch(item);
            $scope.tempVersion = version;
        	$event.stopPropagation();
        	$rootScope.openContextMenu('#context-menu-version', $event);
    	};
    	
        $scope.edit = function(item) {
            item.edit(function() {
                $('#edit').modal('hide');
            });
        };

        $scope.changePermissions = function(item) {
            item.changePermissions(function() {
                $('#changepermissions').modal('hide');
            });
        };

        $scope.copy = function(item) {
            var samePath = item.tempModel.path.join() === item.model.path.join();
            if (samePath && $scope.fileNavigator.fileNameExists(item.tempModel.name)) {
                item.error = $translate.instant('error_invalid_filename');
                return false;
            }
            item.copy(function() {
                $scope.fileNavigator.refresh();
                $('#copy').modal('hide');
            });
        };

        $scope.compress = function(item) {
            item.compress(function() {
                item.success = true;
                $scope.fileNavigator.refresh();
            }, function() {
                item.success = false;
            });
        };

        $scope.extract = function(item) {
            item.extract(function() {
                item.success = true;
                $scope.fileNavigator.refresh();
            }, function() {
                item.success = false;
            });
        };

        $scope.remove = function(item) {
            item.remove(function() {
                $scope.fileNavigator.refresh();
                $('#delete').modal('hide');
            });
        };

        $scope.rename = function(item) {
            var samePath = item.tempModel.path.join() === item.model.path.join();
            if (samePath && $scope.fileNavigator.fileNameExists(item.tempModel.name)) {
                item.error = $translate.instant('error_invalid_filename');
                return false;
            }
            item.rename(function() {
                $scope.fileNavigator.refresh();
                $('#rename').modal('hide');
            });
        };

        $scope.createFolder = function(item) {
            var name = item.tempModel.name && item.tempModel.name.trim();
            item.tempModel.type = 'dir';
            item.tempModel.path = $scope.fileNavigator.currentPath;
            if (name && !$scope.fileNavigator.fileNameExists(name)) {
                item.createFolder(function() {
                    $scope.fileNavigator.refresh();
                    $('#newfolder').modal('hide');
                });
            } else {
                $scope.temp.error = $translate.instant('error_invalid_filename');
                return false;
            }
        };
        
        $scope.uploadFrom = function(item, temp) {
        	debug.log(item.model.path);
            temp.tempModel.path = item.model.fullPath().split('/');
            debug.log(temp.tempModel.path);
            item.upload(function(data) {
            	var fullPath = temp.tempModel.path;
            	$scope.fileNavigator.currentPath = 
            		fullPath && 
					fullPath[0] === "" ? [] : fullPath.slice(
						0, fullPath.length-1);
            	debug.log('controller.upload.success', 
            		fullPath, $scope.fileNavigator.currentPath);
                $scope.fileNavigator.refresh();
                $('#localselector').modal('hide');
            }, function() {
            	$scope.fileNavigator.refresh();
            	$('#localselector').modal('hide');
        	});
        };
        
        $scope.downloadTo = function(item, dest_path) {
        	//debug.log('controller.downloadTo', item, dest_path);
        	item.downloadTo(dest_path, function(data) {
            	$scope.fileNavigator.refresh();
                $('#downloadselector').modal('hide');
        	}, function() {
            	$scope.fileNavigator.refresh();
                $('#downloadselector').modal('hide');
        	});
        };

        $scope.synchronizeItem = function(item) {
            item.upload(function(data) {
                $scope.fileNavigator.refresh_soft();
            }, function() {
            	$scope.fileNavigator.refresh_soft();
        	});
        };
        
        $scope.uploadFiles = function() {
            $scope.fileUploader.upload(
            	$scope.uploadFileList, 
				$scope.fileNavigator.currentPath).success(function() {
                $scope.fileNavigator.refresh();
                $('#uploadfile').modal('hide');
            }).error(function(data) {
                var errorMsg = data.result && data.result.error || 
                	$translate.instant('error_uploading_files');
                $scope.temp.error = errorMsg;
            });
        };

        $scope.eraseVersion = function(item, version) {
        	debug.log('eraseVersion', item, version);
        	item.removeVersion(version, function(data) {
                $scope.fileNavigator.refresh_soft();
            }, function() {
            	$scope.fileNavigator.refresh_soft();
        	});
        };        
        
        $scope.getQueryParam = function(param) {
            var found;
            window.location.search.substr(1).split("&").forEach(function(item) {
                if (param ===  item.split("=")[0]) {
                    found = item.split("=")[1];
                }
            });
            return found;
        };
                
        $scope.navigateTo = function (itemPath) {
        	$scope.fileNavigator.currentPath = itemPath.split('/'); 
        	$scope.fileNavigator.refresh();
        };
        
        $scope.startRefresherTask = function () {
        	setRefreshCallback(function(data) {
            	$scope.fileNavigator.refresh_soft();
            	$scope.activeTasks.refresh();
        	});
        	startUpdater();
        };
        
        $scope.changeLanguage($scope.getQueryParam('lang'));
        $scope.isWindows = $scope.getQueryParam('server') === 'Windows';

        $scope.fileNavigator.refresh();
    	$scope.activeTasks.refresh();

    	$scope.startRefresherTask();
        
    }]);
})(window, angular, jQuery);