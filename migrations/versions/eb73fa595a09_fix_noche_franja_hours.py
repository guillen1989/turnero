"""fix noche franja hours: 23:00-7:00 → 22:00-8:00

Revision ID: eb73fa595a09
Revises: f7fbad145c0f
Create Date: 2026-06-22 18:00:00.000000
"""
from alembic import op


revision = 'eb73fa595a09'
down_revision = '091df668a14b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE franja_horaria "
        "SET hora_inicio = '22:00:00', hora_fin = '08:00:00' "
        "WHERE nombre = 'Noche' "
        "AND hora_inicio = '23:00:00' AND hora_fin = '07:00:00'"
    )


def downgrade():
    op.execute(
        "UPDATE franja_horaria "
        "SET hora_inicio = '23:00:00', hora_fin = '07:00:00' "
        "WHERE nombre = 'Noche' "
        "AND hora_inicio = '22:00:00' AND hora_fin = '08:00:00'"
    )
