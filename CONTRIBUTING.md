# Contributing Guidelines

Thanks for wanting to help! This document summarises how to report issues,
propose improvements, and submit pull requests for the LinkedIn Bot project.

## 1. Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Be respectful, inclusive, and professional in all community spaces.

## 2. Questions & Bug Reports

1. Search existing issues before opening a new one.
2. When reporting a bug, include:
   - what you ran (`python main.py ...`)
   - log snippets from `logs/laf_<timestamp>.log`
   - screenshots or DOM snippets if selectors failed
   - platform details (OS, Python version, Chrome/Chromium version)

## 3. Proposals & Feature Requests

Open an issue describing the problem you want to solve. It helps to outline:
- the use case or workflow you are addressing
- suggested CLI flags or configuration changes
- any prior art or related PRs/issues

## 4. Development Setup

```bash
uv sync
cp .env.example .env   # create your own secrets
uv run python main.py --help
```

Recommended flags for debugging: `--debug --headless`.

Run the checks before you open a pull request:

```bash
uv run ruff check laf/ main.py tests/ tools/
uv run pytest -q
uv run pyright laf/ main.py
```

## 5. Making Changes

1. Create a feature branch from `main`.
2. Keep changes focused; one feature/fix per PR when possible.
3. Run manual smoke tests (post, comment, engage stream) before submitting.
4. Update docs or help text if behaviour changes.

## 6. Commit Messages

Use short descriptive messages, e.g.:
```
feat: add author mention to engage stream
fix: normalise AI summary whitespace
docs: expand README install section
```

## 7. Pull Request Checklist

- [ ] The checks above pass
- [ ] Tests or manual verification performed (describe in PR)
- [ ] README / docs updated when applicable
- [ ] No secrets or credentials committed
- [ ] Passed linting/formatting (if applicable)

## 8. Licensing

By submitting a contribution, you agree it will be licensed under the
[MIT License](LICENSE.md).

## 9. Need Help?

If you have questions about the contribution process, open an issue and tag it
with `question`. The maintainer will get back to you as soon as possible.
