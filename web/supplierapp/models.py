from django.db import models

class Supplier(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()
