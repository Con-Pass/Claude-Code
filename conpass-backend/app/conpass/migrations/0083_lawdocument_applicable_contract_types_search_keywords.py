from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conpass', '0082_alter_lawfile_file_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='lawdocument',
            name='applicable_contract_types',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='lawdocument',
            name='search_keywords',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
