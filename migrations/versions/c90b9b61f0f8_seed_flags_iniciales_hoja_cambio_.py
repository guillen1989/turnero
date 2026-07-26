"""seed_flags_iniciales_hoja_cambio_supervision_importacion

Revision ID: c90b9b61f0f8
Revises: 7be3ca3f48b9
Create Date: 2026-07-26 12:03:15.989790

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c90b9b61f0f8'
down_revision = '7be3ca3f48b9'
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
                "clave": "hoja_cambio_digital",
                "descripcion": "Hoja de cambios digital (creación, firma y PDF)",
                "activo_global": False,
            },
            {
                "clave": "planilla_supervision_multiunidad",
                "descripcion": "Supervisión de planilla multiunidad y edición de turnos",
                "activo_global": False,
            },
            {
                "clave": "importacion_planilla",
                "descripcion": "Importación de planillas desde archivo iLOG",
                "activo_global": False,
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM feature_flag WHERE clave IN "
               "('hoja_cambio_digital', 'planilla_supervision_multiunidad', 'importacion_planilla')")
