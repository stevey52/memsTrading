## Summary of Changes

- **Automated CI Workflow:** Added GitHub Actions CI configuration to run `test_suite.py` automatically on Python 3.11 and 3.12.
- **Safety & Quality Gates:** Ensures all unit tests, holder distribution checks, and AI council tests pass before merging.

### Test Plan
- [x] Ran unit tests locally (`python -m unittest test_suite.py -v`)
- [x] Verified zero syntax/lint errors across all modules
- [x] Confirmed `.gitignore` protects secrets and environment variables
