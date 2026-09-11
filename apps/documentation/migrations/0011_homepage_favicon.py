from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentation", "0010_documentationchunk"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepage",
            name="favicon",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="documentation/branding/",
                verbose_name="favicon",
            ),
        ),
    ]
