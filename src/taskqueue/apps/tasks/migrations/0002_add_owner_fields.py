from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="owner",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tasks",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="webhookdelivery",
            name="owner",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="webhook_deliveries",
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
    ]
