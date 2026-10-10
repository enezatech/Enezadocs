from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentation", "0014_documentationsite_source_icon_and_source_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepage",
            name="allow_registration",
            field=models.BooleanField(
                default=True,
                help_text="When disabled, new accounts cannot be created (email or social). Existing users can still sign in.",
                verbose_name="allow registration",
            ),
        ),
    ]
