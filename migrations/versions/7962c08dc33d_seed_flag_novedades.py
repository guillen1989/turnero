"""seed_flag_novedades

Revision ID: 7962c08dc33d
Revises: d836f60ead28
Create Date: 2026-08-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7962c08dc33d'
down_revision = 'd836f60ead28'
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
                "clave": "novedades",
                "descripcion": "Feed de novedades (/novedades) con los cambios activos publicados en la unidad",
                "activo_global": True,
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM feature_flag WHERE clave = 'novedades'")
