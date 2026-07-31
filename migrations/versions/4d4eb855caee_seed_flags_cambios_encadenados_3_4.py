"""seed_flags_cambios_encadenados_3_4

Revision ID: 4d4eb855caee
Revises: aec48c5be24e
Create Date: 2026-07-29 22:02:59.820861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d4eb855caee'
down_revision = 'aec48c5be24e'
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
                "clave": "cambios_encadenados",
                "descripcion": "Permite encadenar varios documentos de cambio "
                               "(depende_de) para resolución multi-turno",
                "activo_global": False,
            },
            {
                "clave": "cambios_a_3",
                "descripcion": "Intercambios a 3 bandas (match cíclico de 3 personas)",
                "activo_global": False,
            },
            {
                "clave": "cambios_a_4",
                "descripcion": "Intercambios a 4 bandas (match cíclico de 4 personas)",
                "activo_global": False,
            },
        ],
    )


def downgrade():
    op.execute("DELETE FROM feature_flag WHERE clave IN "
               "('cambios_encadenados', 'cambios_a_3', 'cambios_a_4')")
