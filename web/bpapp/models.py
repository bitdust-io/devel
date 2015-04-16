from django.db import models

class Supplier(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()

class Customer(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
    
class BackupFSItem(models.Model):
    id = models.IntegerField(primary_key=True)
    backupid = models.TextField()
    size = models.IntegerField()
    path = models.TextField()
    
class Friend(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
    name = models.TextField()
    
    