from django.db import models

class Customer(models.Model):
    id = models.IntegerField(primary_key=True)
    idurl = models.URLField()