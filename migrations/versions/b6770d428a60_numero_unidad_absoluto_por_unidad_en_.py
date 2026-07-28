"""numero_unidad absoluto por unidad en documento_cambio

Revision ID: b6770d428a60
Revises: a18f63631b51
Create Date: 2026-07-16 20:04:05.964729

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6770d428a60'
down_revision = 'a18f63631b51'
branch_labels = None
depends_on = None


def upgrade():
    # Patrón de tres pasos (CLAUDE.md): documento_cambio ya tiene filas
    # reales en staging, así que unidad_id/numero_unidad se añaden nullable,
    # se rellenan y solo entonces se convierten a NOT NULL.
    with op.batch_alter_table('documento_cambio', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unidad_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('numero_unidad', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'unidad', ['unidad_id'], ['id'])

    # unidad_id: la del creador del documento (congelada, igual que en el
    # impreso de papel). numero_unidad: orden cronológico (id) dentro de esa
    # unidad, empezando en 1 -- reproduce la numeración que ya llevaba la
    # ayudante a mano para las hojas creadas antes de esta migración.
    op.execute("""
        UPDATE documento_cambio dc
        SET unidad_id = u.unidad_id
        FROM usuario u
        WHERE dc.creado_por_id = u.id
    """)
    op.execute("""
        UPDATE documento_cambio dc
        SET numero_unidad = sub.numero
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY unidad_id ORDER BY id) AS numero
            FROM documento_cambio
        ) AS sub
        WHERE dc.id = sub.id
    """)

    with op.batch_alter_table('documento_cambio', schema=None) as batch_op:
        batch_op.alter_column('unidad_id', nullable=False)
        batch_op.alter_column('numero_unidad', nullable=False)
        batch_op.create_unique_constraint('uq_documento_unidad_numero', ['unidad_id', 'numero_unidad'])


def downgrade():
    with op.batch_alter_table('documento_cambio', schema=None) as batch_op:
        batch_op.drop_constraint('uq_documento_unidad_numero', type_='unique')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('numero_unidad')
        batch_op.drop_column('unidad_id')
