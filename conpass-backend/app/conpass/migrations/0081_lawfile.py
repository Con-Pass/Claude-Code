from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """法令ファイルモデルを追加（FileFieldで初期作成）"""

    dependencies = [
        ('conpass', '0080_lawdocument'),
    ]

    operations = [
        migrations.CreateModel(
            name='LawFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='law_documents/')),
                ('filename', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('law', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='law_files',
                    to='conpass.lawdocument',
                )),
            ],
            options={
                'db_table': 'conpass_lawfile',
                'ordering': ['created_at'],
            },
        ),
    ]
