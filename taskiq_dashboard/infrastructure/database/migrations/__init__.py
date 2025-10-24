import argparse
import os
import pathlib

import alembic
import alembic.config

from taskiq_dashboard.infrastructure.settings import Settings


cli = alembic.config.CommandLine()
cli.parser.formatter_class = argparse.ArgumentDefaultsHelpFormatter


def main() -> None:
    args = cli.parser.parse_args()

    if 'cmd' not in args:
        msg = 'You must specify the command'
        raise ValueError(msg)

    settings = Settings()

    pwd = pathlib.Path(__file__).parent.absolute()
    config_path = pwd / 'alembic.ini'
    config = alembic.config.Config(config_path)
    config.set_main_option('script_location', str(pwd))
    config.set_main_option(
        'sqlalchemy.url',
        settings.postgres.dsn.get_secret_value().replace('%', '%%').replace('postgresql+asyncpg', 'postgresql'),
    )
    config.set_main_option('log_config', os.getenv('LOG_CONFIG_PATH', 'docker/plain-logging.yaml'))
    cli.run_cmd(config, args)
