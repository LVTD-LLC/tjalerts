# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project tries to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Types of changes

**Added** for new features.
**Changed** for changes in existing functionality.
**Deprecated** for soon-to-be removed features.
**Removed** for now removed features.
**Fixed** for any bug fixes.
**Security** in case of vulnerabilities.

## Unreleased
### Fixed
- Prevented missing allauth email address records from crashing settings/email verification paths or sending non-serializable exception objects to Sentry logging.

### Changed
- Updated OpenAI model defaults for HN job extraction to `gpt-5.4-nano`, salary parsing to `gpt-5-nano`, and made chat/embedding model names configurable via Django settings.
- Removed the unsafe btree index on `Company.emails` and bounded the denormalized company email summary to prevent oversized index-row errors during HN job analysis.

## [0.0.3] - 2024-06-25
### Added
- Search for titles and technologies
- Automatic db analyze and vacuum

### Fixed
- Attempted to improve performance of the jobs page

## [0.0.2] - 2024-06-21
### Added
- Titles page
- Titles filter

### Fixed
- Incorrect count of alerts and jobs in the digest email
- Hid the navbar items for mobile


## [0.0.1] - 2024-06-13
### Added
- Page to list technologies
- Headers to point to technologies and companies

### Fixed
- url path which broke Digest view
