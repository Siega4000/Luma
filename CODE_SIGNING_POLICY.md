# Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).

## Team roles

- **Author:** Siega4000 (https://github.com/Siega4000)
- **Reviewer:** Siega4000 (https://github.com/Siega4000)
- **Approver:** Siega4000 (https://github.com/Siega4000)

All team members use multi-factor authentication on GitHub and SignPath.

## Build process

Release binaries are built automatically by GitHub Actions from the
source code in this repository — see `.github/workflows/build.yml`.
No binaries are built or modified manually. Every release is approved
manually before signing.

## Privacy policy

This program will not transfer any information to other networked
systems unless specifically requested by the user or the person
installing or operating it.

Luma downloads media only from the URLs the user enters, checks
pypi.org for updates to its download engine when the user enables that
option, and stores all settings and logs locally in `%APPDATA%\Luma`.
No telemetry, analytics or user data is collected or transmitted.
