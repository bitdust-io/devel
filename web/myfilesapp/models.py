from django.db import models

class BackupFSItem(models.Model):
    id = models.IntegerField(primary_key=True)
    backupid = models.TextField()
    size = models.IntegerField()
    path = models.TextField()
    
    