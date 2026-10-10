from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documentation", "0013_documentationsearchdocument_nav_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentationsite",
            name="source_icon",
            field=models.CharField(
                choices=[
                    ("github", "GitHub"),
                    ("globe", "Globe"),
                    ("external-link", "External link"),
                    ("book", "Book"),
                    ("code", "Code"),
                ],
                default="github",
                max_length=20,
                verbose_name="source link icon",
            ),
        ),
        migrations.AddField(
            model_name="documentationsite",
            name="source_url",
            field=models.URLField(
                blank=True,
                help_text="Open-source repo or product webpage. Leave blank to use the GitHub repository URL for GitHub sources.",
                verbose_name="source link",
            ),
        ),
    ]
