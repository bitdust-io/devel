from django.views import generic

#------------------------------------------------------------------------------ 

from models import BackupFSItem
 
from lib import nameurl

#------------------------------------------------------------------------------ 

class BackupFSItemView(generic.DetailView):
    template_name = 'backupfsitem.html'
    model = BackupFSItem

class BackupFSView(generic.ListView):
    template_name = 'backupfs.html'
    context_object_name = 'backup_fs_items_list'
    
    def get_queryset(self):
        return BackupFSItem.objects.order_by('backupid')

#------------------------------------------------------------------------------ 

    