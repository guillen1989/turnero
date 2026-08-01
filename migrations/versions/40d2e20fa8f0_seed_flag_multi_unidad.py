"""seed_flag_multi_unidad

Revision ID: 40d2e20fa8f0
Revises: d6587fceae8a
Create Date: 2026-08-01 17:36:16.061734

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '40d2e20fa8f0'
down_revision = 'd6587fceae8a'
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
                "clave": "multi_unidad",
                "descripcion": "Usuarios en varios servicios (unidades): selector de "
                               "unidad, registro multi-servicio, gestión de servicios "
                               "en perfil y etiquetas de unidad en notificaciones/push",
                "activo_global": True,
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM feature_flag WHERE clave = 'multi_unidad'")
