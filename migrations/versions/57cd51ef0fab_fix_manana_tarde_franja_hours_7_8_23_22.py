"""fix manana tarde franja hours: 7->8, 23->22

Revision ID: 57cd51ef0fab
Revises: e93a778414b8
Create Date: 2026-06-25 12:19:21.369705

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '57cd51ef0fab'
down_revision = 'e93a778414b8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE franja_horaria SET hora_inicio = '08:00:00' "
        "WHERE nombre = 'Mañana' AND hora_inicio = '07:00:00'"
    )
    op.execute(
        "UPDATE franja_horaria SET hora_fin = '22:00:00' "
        "WHERE nombre = 'Tarde' AND hora_fin = '23:00:00'"
    )


def downgrade():
    op.execute(
        "UPDATE franja_horaria SET hora_inicio = '07:00:00' "
        "WHERE nombre = 'Mañana' AND hora_inicio = '08:00:00'"
    )
    op.execute(
        "UPDATE franja_horaria SET hora_fin = '23:00:00' "
        "WHERE nombre = 'Tarde' AND hora_fin = '22:00:00'"
    )
