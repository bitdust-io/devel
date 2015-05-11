from django.db import models

class Identity(models.Model):
    id = models.IntegerField(primary_key=True)
    # id = models.CharField(max_length=255, primary_key=True)
    idurl = models.URLField()
    src = models.TextField()
