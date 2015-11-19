Date.prototype.isValid = function () {
    // An invalid date object returns NaN for getTime() and NaN is the only
    // object not strictly equal to itself.
    return this.getTime() === this.getTime();
}; 

var trimLeftRegExp = new RegExp("^[/]+");
var slashReplaceRegExp = new RegExp("/([^\/])\/([^\/])/g");

(function(window, angular, $) {
    "use strict";
    angular.module('FileManagerApp').factory('item', [
        '$http', '$translate', 'fileManagerConfig', 'chmod', 
	    function($http, $translate, fileManagerConfig, Chmod) {

        var Item = function(model) {
            var rawModel = {
                name: model && model.name || '',
                path: model && model.dirpath && model.dirpath.replace(slashReplaceRegExp,"$1//$2").split('/') || [],
                id: model && model.id || '',
                type: model && model.type || 'file',
                size: model && model.size || 0,
                date: model && model.date || '',
                perms: new Chmod(model && model.rights),
                content: model && model.content || '',
                status: model && model.status || '',
                has_childs: model && model.has_childs || false,
                versions: model && model.versions || [],
                recursive: false,
                fullPath: function() {
                	return (this.path.join('/') + '/' + this.name).replace(trimLeftRegExp, "");
                }
            };

            this.error = '';
            this.inprocess = false;

            this.model = angular.copy(rawModel);
            this.tempModel = angular.copy(rawModel);

            //debug.log('Item', model && model.dirpath, this.model.id, this.model.name, this.model.path, this.model.fullPath());
        };
        
        Item.prototype.update_soft = function(model) {
        	this.model.name = model.name || '';
        	this.model.path = model.dirpath.replace(slashReplaceRegExp,"$1//$2").split('/') || [];
        	this.model.id = model.id || '';
        	this.model.type = model.type || 'file';
        	this.model.size = model.size || 0;
        	this.model.date = model.date || '';
        	this.model.has_childs = model.has_childs || false;
        	this.model.versions = model.versions || [];
            //this.model = angular.copy(this.tempModel);
        	//debug.log('update_model', this.model);
        };

        Item.prototype.update = function() {
            angular.extend(this.model, angular.copy(this.tempModel));
            return this;
        };

        Item.prototype.revert = function() {
            angular.extend(this.tempModel, angular.copy(this.model));
            this.error = '';
            return this;
        };

        Item.prototype.defineCallback = function(data, success, error) {
            /* Check if there was some error in a 200 response */
        	//debug.log('defineCallback:', data, data.result.error);
            var self = this;
            if (data.result && data.result.error) {
                self.error = data.result.error;
                return typeof error === 'function' && error(data);
            }
            if (data.error) {
                self.error = data.error.message;
                return typeof error === 'function' && error(data);
            }
            self.update();
            return typeof success === 'function' && success(data);
        };

        Item.prototype.createFolder = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "addfolder",
                path: self.tempModel.path.join('/'),
                name: self.tempModel.name
            }};

            if (self.tempModel.name.trim()) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.createFolderUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_creating_folder');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };

        Item.prototype.upload = function(success, error) {
            var self = this;
            var data = { params: {
                mode: "upload",
                path: self.tempModel.fullPath()
                // path: self.tempModel.path.join('/') + '/' + self.tempModel.name
            }};
            //debug.log('item.upload', self.tempModel.name, self.tempModel.fullPath());
            if (self.tempModel.name.trim()) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.uploadUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_creating_file_folder');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };
        
        Item.prototype.downloadTo = function(dest_path, success, error) {
            var self = this;
            var data = {params: {
                mode: "download",
                dest_path: dest_path,
                //id: self.model.id,
                backupid: self.model.versions[0].backupid, 
                name: self.model.name,
                overwrite: true,
            }};
            debug.log('item.downloadTo', self, data);
            if (dest_path) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.downloadUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_downloading_file_folder');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };
                
        Item.prototype.rename = function(success, error) {
            var self = this;
            var data = {params: {
                "mode": "rename",
                "path": self.model.fullPath(),
                "newPath": self.tempModel.fullPath()
            }};
            if (self.tempModel.name.trim()) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.renameUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_renaming');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };

        Item.prototype.copy = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "copy",
                path: self.model.fullPath(),
                newPath: self.tempModel.fullPath()
            }};
            if (self.tempModel.name.trim()) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.copyUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_copying');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };

        Item.prototype.compress = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "compress",
                path: self.model.fullPath(),
                destination: self.tempModel.fullPath()
            }};
            if (self.tempModel.name.trim()) {
                self.inprocess = true;
                self.error = '';
                return $http.post(fileManagerConfig.compressUrl, data).success(function(data) {
                    self.defineCallback(data, success, error);
                }).error(function(data) {
                    self.error = data.result && data.result.error ?
                        data.result.error:
                        $translate.instant('error_compressing');
                    typeof error === 'function' && error(data);
                })['finally'](function() {
                    self.inprocess = false;
                });
            }
        };

        Item.prototype.extract = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "extract",
                path: self.model.fullPath(),
                sourceFile: self.model.fullPath(),
                destination: self.tempModel.fullPath()
            }};

            self.inprocess = true;
            self.error = '';
            return $http.post(fileManagerConfig.extractUrl, data).success(function(data) {
                self.defineCallback(data, success, error);
            }).error(function(data) {
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_extracting');
                typeof error === 'function' && error(data);
            })["finally"](function() {
                self.inprocess = false;
            });
        };

        Item.prototype.download = function(preview) {
            var self = this;
            var data = {
                mode: "download",
                preview: preview,
                path: self.model.fullPath(),
                backupid: self.model.versions[0].backupid, 
            };
            var url = [fileManagerConfig.downloadFileUrl, $.param(data)].join('?');
            //if (self.model.type !== 'dir') {
            window.open(url, '_blank', '');
            //}
        };

        Item.prototype.preview = function() {
            var self = this;
            return self.download(true);
        };

        Item.prototype.getContent = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "editfile",
                path: self.tempModel.fullPath()
            }};
            self.inprocess = true;
            self.error = '';
            return $http.post(fileManagerConfig.getContentUrl, data).success(function(data) {
                self.tempModel.content = self.model.content = data.result;
                self.defineCallback(data, success, error);
            }).error(function(data) {
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_getting_content');
                typeof error === 'function' && error(data);
            })['finally'](function() {
                self.inprocess = false;
            });
        };

        Item.prototype.remove = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "delete",
                id: self.tempModel.id,
            }};
            self.inprocess = true;
            self.error = '';
            return $http.post(fileManagerConfig.removeUrl, data).success(function(data) {
                self.defineCallback(data, success, error);
            }).error(function(data) {
            	//debug.log('delete.error:', data, data.result.error);
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_deleting');
                typeof error === 'function' && error(data);
            })['finally'](function() {
                self.inprocess = false;
            });
        };
        
        Item.prototype.removeVersion = function(version, success, error) {
            var self = this;
            var data = { params: {
                mode: "deleteversion",
                backupid: version.backupid,
            }};
            self.inprocess = true;
            self.error = '';
            return $http.post(fileManagerConfig.removeVersionUrl, data).success(function(data) {
                self.defineCallback(data, success, error);
            }).error(function(data) {
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_deleting_version');
                typeof error === 'function' && error(data);
            })['finally'](function() {
                self.inprocess = false;
            });
        };        

        Item.prototype.edit = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "savefile",
                content: self.tempModel.content,
                path: self.tempModel.fullPath()
            }};
            self.inprocess = true;
            self.error = '';

            return $http.post(fileManagerConfig.editUrl, data).success(function(data) {
                self.defineCallback(data, success, error);
            }).error(function(data) {
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_modifying');
                typeof error === 'function' && error(data);
            })['finally'](function() {
                self.inprocess = false;
            });
        };

        Item.prototype.changePermissions = function(success, error) {
            var self = this;
            var data = {params: {
                mode: "changepermissions",
                path: self.tempModel.fullPath(),
                perms: self.tempModel.perms.toOctal(),
                permsCode: self.tempModel.perms.toCode(),
                recursive: self.tempModel.recursive
            }};
            self.inprocess = true;
            self.error = '';
            return $http.post(fileManagerConfig.permissionsUrl, data).success(function(data) {
                self.defineCallback(data, success, error);
            }).error(function(data) {
                self.error = data.result && data.result.error ?
                    data.result.error:
                    $translate.instant('error_changing_perms');
                typeof error === 'function' && error(data);
            })['finally'](function() {
                self.inprocess = false;
            });
        };

        Item.prototype.isFolder = function() {
            return this.model.type === 'dir';
        };

        Item.prototype.isDrive = function() {
            return this.model.type === 'dir' && this.model.name.length == 2 && this.model.name[1] == ':';
        };

        Item.prototype.isEditable = function() {
            return !this.isFolder() && fileManagerConfig.isEditableFilePattern.test(this.model.name);
        };

        Item.prototype.isImage = function() {
            return fileManagerConfig.isImageFilePattern.test(this.model.name);
        };

        Item.prototype.isCompressible = function() {
            return this.isFolder();
        };

        Item.prototype.isExtractable = function() {
            return !this.isFolder() && fileManagerConfig.isExtractableFilePattern.test(this.model.name);
        };
        
        Item.prototype.hasChilds = function() {
            return this.model.has_childs;
        };
        
        Item.prototype.hasVersions = function() {
            return this.model.versions.length > 0;
        };

        Item.prototype.isLocal = function() {
            return this.model.id == '';
        };
        
        Item.prototype.sizeKB = function() {
            return Math.round(this.model.size / 1024, 1);
        };
        
        Item.prototype.versionClassSelector = function(version) {
        	var status = parseInt(version.status.replace('%', ''));
        	if (status < 75) return 'btn-danger';
        	if (status < 95) return 'btn-warning';
        	return 'btn-success';
        };

        return Item;
    }]);
})(window, angular, jQuery);
