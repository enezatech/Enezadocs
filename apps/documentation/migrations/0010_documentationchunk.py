from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documentation', '0009_mcptoken_token_alter_mcptoken_token_hash'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentationChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=1000, verbose_name='path')),
                ('ordinal', models.PositiveIntegerField(default=0, verbose_name='ordinal')),
                ('heading', models.CharField(blank=True, max_length=300, verbose_name='heading')),
                ('content', models.TextField(blank=True, verbose_name='content')),
                ('embedding', models.BinaryField(blank=True, null=True, verbose_name='embedding')),
                ('token_count', models.PositiveIntegerField(default=0, verbose_name='token count')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='search_chunks', to='documentation.documentationsource', verbose_name='source')),
            ],
            options={
                'verbose_name': 'documentation chunk',
                'verbose_name_plural': 'documentation chunks',
                'ordering': ['path', 'ordinal'],
                'indexes': [models.Index(fields=['source', 'path'], name='doc_chunk_source_path_idx')],
                'constraints': [models.UniqueConstraint(fields=('source', 'path', 'ordinal'), name='unique_chunk_source_path_ordinal')],
            },
        ),
    ]
