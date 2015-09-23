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
        editUrl: "/filemanager/bridge",
        getContentUrl: "/filemanager/bridge",
        //addFileFolderUrl: "/filemanager/bridge",
        createFolderUrl: "/filemanager/bridge",
        downloadFileUrl: "/filemanager/bridge",
        compressUrl: "/filemanager/bridge",
        extractUrl: "/filemanager/bridge",
        permissionsUrl: "/filemanager/bridge",
        
        allowedActions: {
            rename: true,
            copy: true,
            edit: true,
            changePermissions: true,
            compress: true,
            compressChooseName: true,
            extract: true,
            download: true,
            preview: true,
            remove: true
        },

        enablePermissionsRecursive: true,

        isEditableFilePattern: /\.(txt|html?|aspx?|ini|pl|py|md|css|js|log|htaccess|htpasswd|json|sql|xml|xslt?|sh|rb|as|bat|cmd|coffee|php[3-6]?|java|c|cbl|go|h|scala|vb)$/i,
        isImageFilePattern: /\.(jpe?g|gif|bmp|png|svg|tiff?)$/i,
        isExtractableFilePattern: /\.(gz|tar|rar|g?zip)$/i,
        
        tplPath: '/filemanagerapp/templates'
    });
})(angular);
