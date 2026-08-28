"""seed_flag_asistente_parser

Revision ID: d836f60ead28
Revises: 17ccced54ffc
Create Date: 2026-08-28 13:47:24.396623

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd836f60ead28'
down_revision = '17ccced54ffc'
branch_labels = None
depends_on = None


def upgrade():
    feature_flag = sa.table(
        "feature_flag",
        sa.column("clave", sa.String),
        sa.column("descripcion", sa.String),
        sa.column("activo_global", sa.Boolean),
    )
    op.bulk_insert(
        feature_flag,
        [
            {
                "clave": "asistente_parser",
                "descripcion": "Asistente de parseo de mensajes de WhatsApp al publicar",
                "activo_global": False,
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM feature_flag WHERE clave = 'asistente_parser'")
