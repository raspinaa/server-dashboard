from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0005_update_upload_audit_indexes')]
    operations = [
        migrations.AddField(model_name='project', name='deleted_at', field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name='project', name='deleted_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='deleted_projects', to=settings.AUTH_USER_MODEL)),
    ]
