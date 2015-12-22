(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp')
	.controller('FileManagerCtrl', [
    '$scope', '$rootScope', '$translate', '$cookies', '$interval', '$http', 
	'fileManagerConfig', 'item', 'fileNavigator', /*'FileUploader',*/ 'ActiveTasks',  
    function($scope, $rootScope, $translate, $cookies, $interval, $http, 
    		fileManagerConfig, Item, FileNavigator, /*FileUploader,*/ ActiveTasks) {

        $scope.config = fileManagerConfig;
        $scope.appName = fileManagerConfig.appName;
        $scope.orderProp = ['model.type', 'model.name'];
        $scope.query = '';
        $scope.temp = new Item();
        $scope.tempVersion = null;
        $scope.fileNavigator = new FileNavigator();
        //$scope.fileUploader = FileUploader;
        $scope.activeTasks = new ActiveTasks();
        $scope.uploadFileList = [];
        $scope.viewTemplate = $cookies.viewTemplate || 'main-table.html';

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
        	//debug.log('smartClick', item.isFolder());
            if (item.isFolder() && $scope.fileNavigator.treeView) {
                if (! $scope.fileNavigator.folderClick(item)) {
            		//$scope.touch(item);
                	//$rootScope.openContextMenu('#context-menu-folder', $event);
                }
            	$event.stopPropagation();
                return;
            };
    		//$scope.touch(item);
        	//$rootScope.openContextMenu('#context-menu-item', $event);
        };

        $scope.smartRightClick = function(item, $event) {
        	$event.stopPropagation();
    		$scope.touch(item);
        	if (item.isFolder()) {
            	$rootScope.openContextMenu('#context-menu-folder', $event);
        	} else {
        		$rootScope.openContextMenu('#context-menu-item', $event);
        	}
        };

        $scope.smartClickVersion = function(item, version, $event) {
        	$event.stopPropagation();
    		$scope.touch(item);
            $scope.tempVersion = version;
        	$rootScope.openContextMenu('#context-menu-version', $event);
        };

        $scope.smartRightClickVersion = function(item, version, $event) {
        	//debug.log('smartRightClickVersion', item, version);
        	$event.stopPropagation();
    		$scope.touch(item);
            $scope.tempVersion = version;
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
        	//debug.log('uploadFrom', item.model.path);
            temp.tempModel.path = item.model.fullPath().split('/');
            debug.log('uploadFrom', temp.tempModel.path);
            item.upload(function(data) {
            	var fullPath = temp.tempModel.path;
            	$scope.fileNavigator.currentPath = 
            		fullPath && 
					fullPath[0] === "" ? [] : fullPath.slice(
						0, fullPath.length-1);
            	debug.log('controller.upload.success', 
            		fullPath, $scope.fileNavigator.currentPath);
                $scope.fileNavigator.request_stats();
            	$scope.activeTasks.refresh();
                $scope.fileNavigator.refresh();
                $('#localselector').modal('hide');
            }, function() {
                $scope.fileNavigator.request_stats();
            	$scope.activeTasks.refresh();
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
        
        $scope.exploreItem = function(item) {
        };
        
        $scope.uploadFiles = function() {
        	/*
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
            */
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
        
        $scope.initialized = function() {
        	return fileManagerConfig.stats && fileManagerConfig.stats['timestamp'];
        };
        
        $scope.stat = function(key) {
        	if (fileManagerConfig.stats && fileManagerConfig.stats[key]) {
        		return fileManagerConfig.stats[key];
        	}
        	return undefined;
        };
        
        $scope.hasIndexedItems = function() {
        	return false;
        	if (!fileManagerConfig.stats)
        		return false;
        	var bytes_indexed = fileManagerConfig.stats.bytes_indexed;
        	var items_count = fileManagerConfig.stats.items_count;
        	if (bytes_indexed == undefined || items_count == undefined) 
        		return false;
        	//debug.log('hasIndexedItems', bytes_indexed, items_count);
        	return parseInt(bytes_indexed) > 0 || parseInt(items_count) > 1;
        };
                
        $scope.navigateTo = function (itemPath) {
        	$scope.fileNavigator.currentPath = itemPath.split('/'); 
        	$scope.fileNavigator.refresh();
        };
        
        $scope.startRefresherTask = function () {
        	setRefreshCallback(function(data) {
        		// debug.log('refresh', data);
        		if (data.backupID || data.pathID) {
        			$scope.fileNavigator.refresh_soft();
                	$scope.activeTasks.refresh();
            	} else if (data.automat) {
            		$scope.fileNavigator.request_debug_info();
            	} else if (data.contact || data.supplier || data.customer) {
            		$scope.fileNavigator.request_stats_soft();
            	}
        	});
        	startUpdater();
        };
        
        $scope.changeLanguage($scope.getQueryParam('lang'));
        $scope.isWindows = $scope.getQueryParam('server') === 'Windows';

        $scope.fileNavigator.request_configs();
        $scope.fileNavigator.request_stats();
        $scope.fileNavigator.refresh();
    	$scope.activeTasks.refresh();
        $scope.fileNavigator.request_debug_info();

    	$scope.startRefresherTask();
        
    }]);
})(window, angular, jQuery);
