from django.db import migrations, models
import django.db.models.expressions


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0002_add_owner_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="idempotency_key",
            field=models.CharField(max_length=128, blank=True, null=True, db_index=True),
        ),
        migrations.AddConstraint(
            model_name="task",
            constraint=models.UniqueConstraint(
                fields=("owner", "idempotency_key"),
                condition=models.Q(("idempotency_key__isnull", False)),
                name="uniq_task_owner_idempotency_key",
            ),
        ),
    ]
