from django.apps import AppConfig
from django.contrib.auth import models as auth_models
from django.contrib.auth.management.commands import createsuperuser
from django.db.models import signals


USERNAME = "local_admin"
PASSWORD = "password"


def create_testuser(**kwargs):
    try:
        auth_models.User.objects.get(username=USERNAME)
    except auth_models.User.DoesNotExist:
        auth_models.User.objects.create_superuser(USERNAME, 'local_admin@localhost', PASSWORD)


class ASiteAppConfig(AppConfig):
    name = __package__

    def ready(self):
        # if not settings.DEBUG:
        #     return
        # Prevent interactive question about wanting a superuser created
        signals.post_syncdb.disconnect(createsuperuser, sender=auth_models,
            dispatch_uid='django.contrib.auth.management.create_superuser')
        signals.post_syncdb.connect(create_testuser, sender=auth_models,
            dispatch_uid='common.models.create_testuser')
            
            
            