import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0004_machine_interfaces')]
    operations = [
        migrations.AddIndex(model_name='audit', index=models.Index(fields=['created_at', 'id'], name='audit_time_id_idx')),
        migrations.AddIndex(model_name='audit', index=models.Index(fields=['event', 'created_at'], name='audit_event_time_idx')),
        migrations.CreateModel(name='UpdateUpload', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('version', models.CharField(max_length=40)), ('sha256', models.CharField(max_length=64)),
            ('status', models.CharField(default='pending', max_length=20)), ('error', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
