"""añade columnas pub sintetica

Revision ID: e8e3d3c815bd
Revises: 653ed2f64432
Create Date: 2026-06-26 21:59:42.511647

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8e3d3c815bd'
down_revision = '653ed2f64432'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('es_sintetica', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('sintetica_pub_a_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sintetica_pub_b_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_sintetica_pub_a', 'publicacion_cambio', ['sintetica_pub_a_id'], ['id'])
        batch_op.create_foreign_key('fk_sintetica_pub_b', 'publicacion_cambio', ['sintetica_pub_b_id'], ['id'])

    op.execute("UPDATE publicacion_cambio SET es_sintetica = FALSE WHERE es_sintetica IS NULL")

    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.alter_column('es_sintetica', nullable=False)

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('publicacion_cambio', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sintetica_pub_b', type_='foreignkey')
        batch_op.drop_constraint('fk_sintetica_pub_a', type_='foreignkey')
        batch_op.drop_column('sintetica_pub_b_id')
        batch_op.drop_column('sintetica_pub_a_id')
        batch_op.drop_column('es_sintetica')

    # ### end Alembic commands ###
