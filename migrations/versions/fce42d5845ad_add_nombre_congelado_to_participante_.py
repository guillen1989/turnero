"""add nombre_congelado to participante_documento_cambio

Revision ID: fce42d5845ad
Revises: 7ed9c5cc5e02
Create Date: 2026-07-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fce42d5845ad'
down_revision = '7ed9c5cc5e02'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable a propósito, no solo por el patrón de 3 pasos: los documentos
    # en borrador/pendiente_firmas legítimamente no tienen nombre congelado
    # todavía (se rellena al completarse el documento). Sin backfill: el
    # proyecto aún no ha llegado a producción, no hay filas existentes que
    # migrar.
    with op.batch_alter_table('participante_documento_cambio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nombre_congelado', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('participante_documento_cambio', schema=None) as batch_op:
        batch_op.drop_column('nombre_congelado')
