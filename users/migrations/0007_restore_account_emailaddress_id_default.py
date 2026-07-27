# ruff: noqa: RUF012

from django.db import migrations


def restore_account_emailaddress_id_default(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT is_identity
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'account_emailaddress'
              AND column_name = 'id'
            """
        )
        column = cursor.fetchone()

    if column and column[0] == "YES":
        return

    schema_editor.execute(
        """
        LOCK TABLE account_emailaddress IN ACCESS EXCLUSIVE MODE;

        CREATE SEQUENCE IF NOT EXISTS account_emailaddress_id_seq AS integer;
        ALTER SEQUENCE account_emailaddress_id_seq
            OWNED BY account_emailaddress.id;

        DO $$
        DECLARE
            maximum_id bigint;
            sequence_last_value bigint;
            sequence_is_called boolean;
        BEGIN
            SELECT MAX(id)
            INTO maximum_id
            FROM account_emailaddress;

            SELECT last_value, is_called
            INTO sequence_last_value, sequence_is_called
            FROM account_emailaddress_id_seq;

            IF maximum_id IS NULL THEN
                PERFORM setval(
                    'account_emailaddress_id_seq',
                    sequence_last_value,
                    sequence_is_called
                );
            ELSE
                PERFORM setval(
                    'account_emailaddress_id_seq',
                    GREATEST(maximum_id, sequence_last_value),
                    true
                );
            END IF;
        END
        $$;

        ALTER TABLE account_emailaddress
            ALTER COLUMN id
            SET DEFAULT nextval('account_emailaddress_id_seq'::regclass);
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0009_emailaddress_unique_primary_email"),
        ("users", "0006_subscriber_owner"),
    ]

    operations = [
        migrations.RunPython(
            restore_account_emailaddress_id_default,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
