"""añade unidad_id a notificacion

Revision ID: c56189474f56
Revises: def6b117664c
Create Date: 2026-07-31 14:01:07.331850

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c56189474f56'
down_revision = 'def6b117664c'
branch_labels = None
depends_on = None


def upgrade():
    # 1. añadir como nullable
    with op.batch_alter_table('notificacion', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unidad_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'unidad', ['unidad_id'], ['id'])

    # 2. backfill con la unidad principal del usuario destino
    op.execute(
        "UPDATE notificacion SET unidad_id = u.unidad_id "
        "FROM usuario u WHERE notificacion.usuario_id = u.id"
    )

    # 3. convertir a NOT NULL
    with op.batch_alter_table('notificacion', schema=None) as batch_op:
        batch_op.alter_column('unidad_id', nullable=False)


def downgrade():
    with op.batch_alter_table('notificacion', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('unidad_id')
