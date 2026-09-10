import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def forwards(apps, schema_editor):
    """Convert each existing token into its own scoped MCP server."""
    MCPToken = apps.get_model("documentation", "MCPToken")
    MCPServer = apps.get_model("documentation", "MCPServer")

    for token in MCPToken.objects.all():
        base = slugify(token.name) or f"server-{token.pk}"
        slug = base
        counter = 1
        while MCPServer.objects.filter(slug=slug).exists():
            counter += 1
            slug = f"{base}-{counter}"
        server = MCPServer.objects.create(
            name=token.name or slug,
            slug=slug,
            site_id=token.site_id,
            section_id=token.section_id,
            group_id=token.group_id,
            enabled=token.enabled,
        )
        token.server_id = server.pk
        token.save(update_fields=["server"])


class Migration(migrations.Migration):

    dependencies = [
        ("documentation", "0007_mcptoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="MCPServer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="name")),
                (
                    "slug",
                    models.SlugField(
                        help_text=(
                            "URL segment for the endpoint, addressed as "
                            "MCP_PATH/<slug>/."
                        ),
                        unique=True,
                        verbose_name="slug",
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
                ("enabled", models.BooleanField(default=True, verbose_name="enabled")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Optional group node inside the section; empty grants "
                            "the whole section."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="documentation.documentationnode",
                        verbose_name="group",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Optional top-level section node; empty grants the whole "
                            "site."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="documentation.documentationnode",
                        verbose_name="section",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mcp_servers",
                        to="documentation.documentationsite",
                        verbose_name="site",
                    ),
                ),
            ],
            options={
                "verbose_name": "MCP server",
                "verbose_name_plural": "MCP servers",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="mcptoken",
            name="server",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tokens",
                to="documentation.mcpserver",
                verbose_name="server",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="mcptoken",
            name="server",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tokens",
                to="documentation.mcpserver",
                verbose_name="server",
            ),
        ),
        migrations.RemoveField(
            model_name="mcptoken",
            name="group",
        ),
        migrations.RemoveField(
            model_name="mcptoken",
            name="section",
        ),
        migrations.RemoveField(
            model_name="mcptoken",
            name="site",
        ),
    ]
