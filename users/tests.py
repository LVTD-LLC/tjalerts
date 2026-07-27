from importlib import import_module
from unittest import skipUnless
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from users.api_keys import authenticate_api_key, rotate_user_api_key
from users.models import UserAPIKey


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

    def test_settings_includes_api_key_management(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("settings"))

        assert response.status_code == 200
        self.assertContains(response, "API key")
        self.assertContains(response, "Generate API key")

    def test_api_key_generation_requires_login(self):
        response = self.client.post(reverse("generate_api_key"))

        assert response.status_code == 302
        assert response.url.startswith(reverse("account_login"))

    def test_generating_api_key_shows_it_once_without_storing_raw_value(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("generate_api_key"))

        assert response.status_code == 200
        api_key = response.context["generated_api_key"]
        assert api_key.startswith("tja_")
        self.assertContains(response, api_key)
        self.assertEqual(response.headers["Cache-Control"], "max-age=0, no-cache, no-store, must-revalidate, private")
        key_record = UserAPIKey.objects.get(user=user)
        assert api_key not in key_record.key_hash
        assert authenticate_api_key(api_key) == user

        settings_response = self.client.get(reverse("settings"))
        self.assertNotContains(settings_response, api_key)
        self.assertContains(settings_response, f"{key_record.key_prefix}…")

    def test_rotating_api_key_invalidates_the_previous_key(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        first_response = self.client.post(reverse("generate_api_key"))
        second_response = self.client.post(reverse("generate_api_key"))

        first_api_key = first_response.context["generated_api_key"]
        second_api_key = second_response.context["generated_api_key"]
        assert first_api_key != second_api_key
        assert authenticate_api_key(first_api_key) is None
        assert authenticate_api_key(second_api_key) == user
        assert UserAPIKey.objects.filter(user=user).count() == 1

    def test_failed_response_render_preserves_the_previous_key(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        _, previous_api_key = rotate_user_api_key(user)
        self.client.force_login(user)

        with (
            patch("users.views.capture_user_event") as capture_event,
            patch("users.views.render", side_effect=RuntimeError("render failed")),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("generate_api_key"))

        capture_event.assert_not_called()
        assert authenticate_api_key(previous_api_key) == user

    def test_api_key_rotation_event_is_sent_after_commit(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        with (
            patch("users.views.capture_user_event") as capture_event,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(reverse("generate_api_key"))

        assert response.status_code == 200
        capture_event.assert_called_once_with(user, "api key rotated")


class APIKeyTests(TestCase):
    def test_inactive_user_cannot_authenticate(self):
        user = get_user_model().objects.create_user(username="inactive", is_active=False)
        _, api_key = rotate_user_api_key(user)

        assert authenticate_api_key(api_key) is None


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
        assert "IF column_is_identity THEN RETURN" in normalized_sql
        assert "ALTER COLUMN id SET DEFAULT" in normalized_sql

        sqlite_editor = SchemaEditor("sqlite")
        migration.restore_account_emailaddress_id_default(None, sqlite_editor)
        assert sqlite_editor.statements == []


@skipUnless(connection.vendor == "postgresql", "Sequence defaults are PostgreSQL-specific")
class EmailAddressSchemaRepairTests(TestCase):
    def test_repair_leaves_a_working_identity_column_unchanged(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT is_identity
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'account_emailaddress'
                  AND column_name = 'id'
                """
            )
            if cursor.fetchone()[0] != "YES":
                self.skipTest("Test database does not use an identity column")

        migration = import_module("users.migrations.0007_restore_account_emailaddress_id_default")
        migration.restore_account_emailaddress_id_default(None, self.SchemaEditor(connection))

        user = get_user_model().objects.create_user(
            username="identity-schema-test",
            email="identity-schema-test@example.com",
            password="password",
        )
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=False,
        )

        assert email_address.id is not None

    def test_repair_migration_restores_missing_email_address_id_default(self):
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE account_emailaddress ALTER COLUMN id DROP IDENTITY IF EXISTS")
            cursor.execute("ALTER TABLE account_emailaddress ALTER COLUMN id DROP DEFAULT")

        migration = import_module("users.migrations.0007_restore_account_emailaddress_id_default")
        migration.restore_account_emailaddress_id_default(None, self.SchemaEditor(connection))

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

    class SchemaEditor:
        def __init__(self, database_connection):
            self.connection = database_connection

        def execute(self, sql):
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
