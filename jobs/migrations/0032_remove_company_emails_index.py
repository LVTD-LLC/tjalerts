# Generated manually to remove an unsafe btree index on a large text field.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0031_technology_index_t_technology_slug"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="company",
            name="index_company_emails",
        ),
    ]
