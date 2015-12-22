(function(angular) {
    "use strict";
    angular.module('FileManagerApp').constant("fileManagerConfig", {
        appName: "",
        defaultLang: "en",

        listUrl: "/filemanager/bridge",
        uploadUrl: "/filemanager/bridge",
        downloadUrl: "/filemanager/bridge",
        renameUrl: "/filemanager/bridge",
        copyUrl: "/filemanager/bridge",
        removeUrl: "/filemanager/bridge",
        removeVersionUrl: "/filemanager/bridge",
        editUrl: "/filemanager/bridge",
        getContentUrl: "/filemanager/bridge",
        createFolderUrl: "/filemanager/bridge",
        downloadFileUrl: "/filemanager/bridge",
        compressUrl: "/filemanager/bridge",
        extractUrl: "/filemanager/bridge",
        permissionsUrl: "/filemanager/bridge",
        tasksUrl: "/filemanager/bridge",
        configUrl: "/filemanager/bridge",
        statsUrl: "/filemanager/bridge",
        debugUrl: "/filemanager/bridge",
        
        localConfig: {},
		
        debugInfo: {},
		
		stats: {},
        
        allowedActions: {
            rename: true,
            copy: true,
            edit: true,
			open: true,
            changePermissions: true,
            compress: true,
            compressChooseName: true,
            extract: true,
            download: true,
            synchronize: true,
            preview: true,
            remove: true,
            tasks: true,
            cancel: true,
			explore: true,
			restore: true,
            eraseversion: true,
            restoreversion: true,
            downloadversion: true,
			watchversion: true,
        },

        enablePermissionsRecursive: true,

        isEditableFilePattern: /\.(txt|html?|aspx?|ini|pl|py|md|css|js|log|htaccess|htpasswd|json|sql|xml|xslt?|sh|rb|as|bat|cmd|coffee|php[3-6]?|java|c|cbl|go|h|scala|vb)$/i,
        isImageFilePattern: /\.(jpe?g|gif|bmp|png|svg|tiff?)$/i,
        isExtractableFilePattern: /\.(gz|tar|rar|g?zip)$/i,
        
        tplPath: '/filemanagerapp/templates'

    });
})(angular);
