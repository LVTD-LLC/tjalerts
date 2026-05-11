from django.test import SimpleTestCase

from jobs.tasks import MAX_COMPANY_EMAILS_LENGTH, merge_company_emails


class CompanyEmailMergeTests(SimpleTestCase):
    def test_merge_company_emails_deduplicates_and_adds_separator(self):
        assert merge_company_emails("a@example.com", "b@example.com, a@example.com") == (
            "a@example.com, b@example.com"
        )

    def test_merge_company_emails_is_bounded(self):
        long_email_blob = "a" * (MAX_COMPANY_EMAILS_LENGTH + 100)

        assert len(merge_company_emails("", long_email_blob)) == MAX_COMPANY_EMAILS_LENGTH
