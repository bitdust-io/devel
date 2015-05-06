from django.db import models

class Identity(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    idurl = models.URLField()
    src = models.TextField()

class Supplier(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()

class Customer(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
    
class Friend(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
    name = models.TextField()
    
class BackupFSItem(models.Model):
    id = models.IntegerField(primary_key=True)
    backupid = models.TextField()
    size = models.IntegerField()
    path = models.TextField()
    
    