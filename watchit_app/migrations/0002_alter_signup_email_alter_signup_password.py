# Generated by Django 5.1.4 on 2024-12-30 07:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("watchit_app", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signup",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
        migrations.AlterField(
            model_name="signup",
            name="password",
            field=models.CharField(max_length=255),
        ),
    ]
