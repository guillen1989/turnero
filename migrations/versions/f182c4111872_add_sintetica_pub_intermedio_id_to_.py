"""add sintetica_pub_intermedio_id to publicacion_cambio

Revision ID: f182c4111872
Revises: 6085c41640ba
Create Date: 2026-07-10 21:37:10.008611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f182c4111872'
down_revision = '6085c41640ba'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sintetica_pub_intermedio_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_sintetica_pub_intermedio', 'publicacion_cambio',
            ['sintetica_pub_intermedio_id'], ['id'],
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sintetica_pub_intermedio', type_='foreignkey')
        batch_op.drop_column('sintetica_pub_intermedio_id')

    # ### end Alembic commands ###
