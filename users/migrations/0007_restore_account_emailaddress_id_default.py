# ruff: noqa: RUF012

from django.db import migrations


def restore_account_emailaddress_id_default(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        DO $$
        DECLARE
            column_is_identity boolean;
            maximum_id bigint;
            sequence_last_value bigint;
            sequence_is_called boolean;
        BEGIN
            SELECT is_identity = 'YES'
            INTO column_is_identity
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'account_emailaddress'
              AND column_name = 'id';

            IF column_is_identity THEN
                RETURN;
            END IF;

            LOCK TABLE account_emailaddress IN ACCESS EXCLUSIVE MODE;

            CREATE SEQUENCE IF NOT EXISTS account_emailaddress_id_seq AS integer;
            ALTER SEQUENCE account_emailaddress_id_seq
                OWNED BY account_emailaddress.id;

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

            ALTER TABLE account_emailaddress
                ALTER COLUMN id
                SET DEFAULT nextval('account_emailaddress_id_seq'::regclass);
        END
        $$;
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
