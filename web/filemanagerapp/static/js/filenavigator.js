(function(angular) {
    "use strict";
    angular.module('FileManagerApp').service('fileNavigator', [
        '$http', 'fileManagerConfig', 'item', '$cookies',  
        function ($http, fileManagerConfig, Item, $cookies) {

        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

        var FileNavigator = function() {
            this.requesting = false;
            this.fileList = [];
            this.currentPath = [];
            this.history = [];
            this.error = '';
            this.targetItem = null;
            this.mode = 'default';
            this.treeView = false;
            if ($cookies.treeView == 'true') {
            	this.treeView = true;
            }
            if ($cookies.currentPath) {
            	this.currentPath = $cookies.currentPath.split('/');
            }
        };
        
        FileNavigator.prototype.switchTreeView = function() {
            //debug.log($cookies.treeView);
        	this.treeView = !this.treeView;
        	if (this.treeView) {
        		$cookies.treeView = 'true';
        	} else {
        		$cookies.treeView = 'false';
        	}
            //debug.log(this.treeView);
            this.goTo(-1);
        };
        
        FileNavigator.prototype.request_configs = function(success, error) {
            var self = this;
            var data = { params: {
                mode: 'config'
            }};
            self.requesting = true;
            fileManagerConfig.localConfig = {};
            self.error = '';
            $http.post(fileManagerConfig.configUrl, data).success(function(data) {
                angular.forEach(data.result, function(conf) {
                    fileManagerConfig.localConfig[conf.key] = conf.value;
                });
                debug.log('request_configs', fileManagerConfig.localConfig);
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

        FileNavigator.prototype.request_stats = function(success, error) {
            var self = this;
            var data = { params: {
                mode: 'stats'
            }};
            self.requesting = true;
            fileManagerConfig.stats = {};
            self.error = '';
            $http.post(fileManagerConfig.statsUrl, data).success(function(data) {
            	fileManagerConfig.stats = data.result;
                debug.log('stats:', fileManagerConfig.stats);
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
        
        FileNavigator.prototype.refresh = function(success, error) {
            var self = this;
            var needed_mode = "list";
            var need_only_Folders = false;
            var path = self.currentPath.join('/');
            if (self.mode != 'default') {
            	needed_mode = "listlocal";
            } else {
	            if (!self.treeView) {
	            	needed_mode = "listall";
	            }
            }
            if (self.mode == 'select_download_path') {
            	need_only_Folders = true;
            }
            var data = { params: {
                mode: needed_mode,
                onlyFolders: need_only_Folders,
                path: path
            }};
            // debug.log('refresh', needed_mode, path);

            self.requesting = true;
            self.fileList = [];
            self.error = '';
            $http.post(fileManagerConfig.listUrl, data).success(function(data) {
                self.fileList = [];
                angular.forEach(data.result, function(file) {
                    self.fileList.push(new Item(file));
                });
                self.requesting = false;
                self.buildTree(path);

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

        FileNavigator.prototype.refresh_soft = function(success, error) {
            var self = this;
            var needed_mode = "list";
            var need_only_Folders = false;
            var path = self.currentPath.join('/');
            if (self.mode != 'default') {
            	needed_mode = "listlocal";
            } else {
	            if (!self.treeView) {
	            	needed_mode = "listall";
	            }
            }
            if (self.mode == 'select_download_path') {
            	need_only_Folders = true;
            }
            var data = {params: {
                mode: needed_mode,
                onlyFolders: need_only_Folders,
                path: path
            }};
            // debug.log('refresh_soft', needed_mode, path);
            //self.requesting = true;
            self.error = '';
            $http.post(fileManagerConfig.listUrl, data).success(function(data) {
                // debug.log('refresh_soft now');
                angular.forEach(data.result, function(file) {
                	//debug.log('		', file);
                	var foundOld = false; 
                    for (var o in self.fileList) {
                        var item = self.fileList[o];
                        if (item.model.id == file.id) {
                        	item.update_soft(file);
                        	foundOld = true;
                        	break;
                        }
                    }
                    if (!foundOld) {
                        self.fileList.push(new Item(file));
                    }
                });
                var to_remove = [];
                for (var o in self.fileList) {
                    var item = self.fileList[o];
                    var foundNew = false;
                    for (var n in data.result) {
                    	var nfile = data.result[n];
                    	if (item.model.id == nfile.id) {
                    		foundNew = true;
                    		break;
                    	}
                    }
                    if (!foundNew) {
                    	to_remove.push(o)
                    }
                }
                for (var o in to_remove) {
                	self.fileList.splice(o, 1);
                }
                //self.requesting = false;
                if (data.error) {
                    self.error = data.error;
                    return typeof error === 'function' && error(data);
                }
                typeof success === 'function' && success(data);
            }).error(function(data) {
                //self.requesting = false;
                typeof error === 'function' && error(data);
            });
        };
        
        FileNavigator.prototype.buildTree = function(path) {
            var self = this;
            function recursive(parent, file, path) {
                var absName = path ? (path + '/' + file.name) : file.name;
                if (parent.name.trim() && path.trim().indexOf(parent.name) !== 0) {
                    parent.nodes = [];
                }
                if (parent.name !== path) {
                    for (var i in parent.nodes) {
                        recursive(parent.nodes[i], file, path);
                    }
                } else {
                    for (var e in parent.nodes) {
                        if (parent.nodes[e].name === absName) {
                            return;
                        }
                    }
                    parent.nodes.push({name: absName, nodes: []});
                }
                parent.nodes = parent.nodes.sort(function(a, b) {
                    return a.name < b.name ? -1 : a.name === b.name ? 0 : 1;
                });
            };

            !self.history.length && self.history.push({name: path, nodes: []});
            for (var o in self.fileList) {
                var item = self.fileList[o];
                item.isFolder() && recursive(self.history[0], item.model, path);
            }
        };

        FileNavigator.prototype.folderClickByName = function(fullPath) {
            var self = this;
            fullPath = fullPath.replace(/^\/*/g, '');
            var splitPath = fullPath.split('/');
            self.currentPath = fullPath && splitPath[0] === "" ? [] : splitPath;
            $cookies.currentPath = fullPath;
            self.refresh();
        };

        FileNavigator.prototype.folderClick = function(item) {
            var self = this;
            if (item && item.model.type === 'dir' && (item.hasChilds() || item.isLocal())) {
                self.currentPath.push(item.model.name);
                $cookies.currentPath = self.currentPath.join('/');
                self.refresh();
                return true;
            } else {
            	return false;
            }
        };

        FileNavigator.prototype.upDir = function() {
            var self = this;
            if (self.currentPath[0]) {
                self.currentPath = self.currentPath.slice(0, -1);
                $cookies.currentPath = self.currentPath.join('/');
                self.refresh();
            }
        };

        FileNavigator.prototype.goTo = function(index) {
            var self = this;
            self.currentPath = self.currentPath.slice(0, index + 1);
            $cookies.currentPath = self.currentPath.join('/');
            self.refresh();
        };

        FileNavigator.prototype.fileNameExists = function(fileName) {
            var self = this;
            for (var item in self.fileList) {
                item = self.fileList[item];
                if (fileName.trim && item.model.name.trim() === fileName.trim()) {
                    return true;
                }
            }
            return false;
        };

        FileNavigator.prototype.listHasFolders = function() {
            var self = this;
            for (var item in self.fileList) {
                if (self.fileList[item].model.type === 'dir') {
                    return true;
                }
            }
            return false;
        };

        FileNavigator.prototype.isEmpty = function() {
            var self = this;
            //debug.log('isEmpty', self.currentPath);
        	if (!self.currentPath[0])
        		return false;
            for (var item in self.fileList) {
                if (self.fileList[item].model.type === 'dir' ||
            		self.fileList[item].model.type === 'file') {
                    return false;
                }
            }
            return true;
        };
        
        return FileNavigator;
    }]);
})(angular);
