from django.db import models

class Friend(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
    name = models.TextField()