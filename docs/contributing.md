---
title: Contributing and Development
---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Setting up local development environment

To run the application locally for development, follow these steps:

1. Clone the repository:

    ```bash
    git clone
    https://github.com/danfimov/taskiq-dashboard.git
    cd taskiq-dashboard
    ```

2. Create a virtual environment, activate it, install dependencies and pre-commit hooks:

    ```bash
    make init
    ```

3. Start a local PostgreSQL instance using Docker:

    ```bash
    make run_infra
    ```

4. Run tailwindcss in watch mode to compile CSS:

    ```bash
    bun run dev
    ```

5. Start the dashboard application:

    ```bash
    make run
    ```

You can see other useful commands by running `make help`.
