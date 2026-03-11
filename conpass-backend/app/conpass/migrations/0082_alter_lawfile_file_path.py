from django.db import migrations, models


class Migration(migrations.Migration):
    """LawFile の FileField を file_path CharField に変更"""

    dependencies = [
        ('conpass', '0081_lawfile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lawfile',
            name='file',
        ),
        migrations.AddField(
            model_name='lawfile',
            name='file_path',
            field=models.CharField(default='', max_length=500),
            preserve_default=False,
        ),
    ]
