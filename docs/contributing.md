---
title: Contributing and Development
---

## Development

This project uses modern Python development tools:

- [uv](https://github.com/astral-sh/uv) — fast Python package installer and resolver
- [ruff](https://github.com/astral-sh/ruff) — extremely fast Python linter and formatter

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/danfimov/taskiq-dashboard.git
cd taskiq-dashboard

# Create a virtual environment (optional but recommended)
make venv

# Install dependencies
make init
```

You can see other useful commands by running `make help`.


## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
