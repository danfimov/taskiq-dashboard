import typing as tp

import sqlalchemy as sa


def label_text(column: tp.Any, key: str) -> sa.ColumnElement[str]:
    """Render a safely quoted label key so generic plans can use expression indexes."""
    return column[sa.literal(key, type_=sa.JSON.JSONStrIndexType(), literal_execute=True)].as_string()
