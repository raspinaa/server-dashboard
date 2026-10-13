from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0003_importdecision_importvalidation')]
    operations = [migrations.AddField(model_name='machine', name='interfaces', field=models.JSONField(default=list, blank=True))]
