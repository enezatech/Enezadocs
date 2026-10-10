from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentation", "0012_alter_homepage_favicon"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentationsearchdocument",
            name="access",
            field=models.CharField(
                default="public",
                max_length=20,
                verbose_name="access",
            ),
        ),
        migrations.AddField(
            model_name="documentationsearchdocument",
            name="nav_label",
            field=models.CharField(
                blank=True,
                max_length=300,
                verbose_name="nav label",
            ),
        ),
        migrations.AddField(
            model_name="documentationsearchdocument",
            name="nav_order",
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name="nav order",
            ),
        ),
    ]
