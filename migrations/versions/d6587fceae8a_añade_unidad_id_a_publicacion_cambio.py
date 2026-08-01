"""añade unidad_id a publicacion_cambio

Revision ID: d6587fceae8a
Revises: 04dc6824eb1a
Create Date: 2026-08-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd6587fceae8a'
down_revision = '04dc6824eb1a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unidad_id', sa.Integer(), nullable=True))

    op.execute(
        "UPDATE publicacion_cambio SET unidad_id = u.unidad_id "
        "FROM usuario u WHERE publicacion_cambio.usuario_id = u.id"
    )

    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.alter_column('unidad_id', nullable=False)
        batch_op.create_foreign_key(None, 'unidad', ['unidad_id'], ['id'])


def downgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('unidad_id')
