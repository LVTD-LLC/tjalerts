from importlib import import_module
from unittest import skipUnless

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class UserSettingsTests(TestCase):
    def test_unverified_email_banner_does_not_promise_alert_delivery(self):
        user = get_user_model().objects.create_user(
            username="reader",
            email="reader@example.com",
            password="password",
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
        self.client.force_login(user)

        response = self.client.get(reverse("settings"))

        assert response.status_code == 200
        self.assertContains(response, "Confirm your account email")
        self.assertNotContains(response, "keep alerts active")


class EmailAddressSchemaRepairMigrationTests(SimpleTestCase):
    def test_repair_runs_only_for_postgresql(self):
        migration = import_module("users.migrations.0007_restore_account_emailaddress_id_default")

        class SchemaEditor:
            def __init__(self, vendor):
                self.connection = type("Connection", (), {"vendor": vendor})()
                self.statements = []

            def execute(self, sql):
                self.statements.append(sql)

        postgresql_editor = SchemaEditor("postgresql")
        migration.restore_account_emailaddress_id_default(None, postgresql_editor)
        assert len(postgresql_editor.statements) == 1
        normalized_sql = " ".join(postgresql_editor.statements[0].split())
        assert "ALTER COLUMN id SET DEFAULT" in normalized_sql

        sqlite_editor = SchemaEditor("sqlite")
        migration.restore_account_emailaddress_id_default(None, sqlite_editor)
        assert sqlite_editor.statements == []


@skipUnless(connection.vendor == "postgresql", "Sequence defaults are PostgreSQL-specific")
class EmailAddressSchemaRepairTests(TestCase):
    def test_repair_migration_restores_missing_email_address_id_default(self):
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE account_emailaddress ALTER COLUMN id DROP DEFAULT")

        migration = import_module("users.migrations.0007_restore_account_emailaddress_id_default")

        class SchemaEditor:
            def __init__(self, database_connection):
                self.connection = database_connection

            def execute(self, sql):
                with self.connection.cursor() as cursor:
                    cursor.execute(sql)

        migration.restore_account_emailaddress_id_default(None, SchemaEditor(connection))

        user = get_user_model().objects.create_user(
            username="signup-schema-test",
            email="signup-schema-test@example.com",
            password="password",
        )
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=False,
        )

        assert email_address.id is not None
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'account_emailaddress'
                  AND column_name = 'id'
                """
            )
            column_default = cursor.fetchone()[0]
        assert "nextval" in column_default
