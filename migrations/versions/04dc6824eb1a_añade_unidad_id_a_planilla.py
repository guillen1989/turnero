"""añade unidad_id a planilla

Revision ID: 04dc6824eb1a
Revises: c56189474f56
Create Date: 2026-08-01 11:02:15.449922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '04dc6824eb1a'
down_revision = 'c56189474f56'
branch_labels = None
depends_on = None


def upgrade():
    _upgrade_tabla(
        'estado_dia_planilla',
        'uq_estado_dia_usuario_fecha',
        'uq_estado_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha', 'unidad_id'],
        'fk_estado_dia_planilla_unidad',
    )
    _upgrade_tabla(
        'nota_dia',
        'uq_nota_dia_usuario_fecha',
        'uq_nota_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha', 'unidad_id'],
        'fk_nota_dia_unidad',
    )
    _upgrade_tabla(
        'planilla_mes',
        'uq_planilla_mes_usuario',
        'uq_planilla_mes_usuario_unidad',
        ['usuario_id', 'anyo', 'mes', 'unidad_id'],
        'fk_planilla_mes_unidad',
    )
    _upgrade_tabla(
        'saliente_dia',
        'uq_saliente_dia_usuario_fecha',
        'uq_saliente_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha', 'unidad_id'],
        'fk_saliente_dia_unidad',
    )
    _upgrade_tabla(
        'turno_planilla',
        'uq_turno_planilla_usuario_fecha_franja',
        'uq_turno_planilla_usuario_fecha_franja_unidad',
        ['usuario_id', 'fecha', 'franja_horaria_id', 'unidad_id'],
        'fk_turno_planilla_unidad',
    )


def downgrade():
    _downgrade_tabla(
        'turno_planilla',
        'uq_turno_planilla_usuario_fecha_franja',
        'uq_turno_planilla_usuario_fecha_franja_unidad',
        ['usuario_id', 'fecha', 'franja_horaria_id'],
        'fk_turno_planilla_unidad',
    )
    _downgrade_tabla(
        'saliente_dia',
        'uq_saliente_dia_usuario_fecha',
        'uq_saliente_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha'],
        'fk_saliente_dia_unidad',
    )
    _downgrade_tabla(
        'planilla_mes',
        'uq_planilla_mes_usuario',
        'uq_planilla_mes_usuario_unidad',
        ['usuario_id', 'anyo', 'mes'],
        'fk_planilla_mes_unidad',
    )
    _downgrade_tabla(
        'nota_dia',
        'uq_nota_dia_usuario_fecha',
        'uq_nota_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha'],
        'fk_nota_dia_unidad',
    )
    _downgrade_tabla(
        'estado_dia_planilla',
        'uq_estado_dia_usuario_fecha',
        'uq_estado_dia_usuario_fecha_unidad',
        ['usuario_id', 'fecha'],
        'fk_estado_dia_planilla_unidad',
    )


def _upgrade_tabla(tabla, old_constraint, new_constraint, columnas, fk_name):
    with op.batch_alter_table(tabla, schema=None) as batch_op:
        batch_op.drop_constraint(old_constraint, type_='unique')

        # Paso 1: añadir nullable
        batch_op.add_column(sa.Column('unidad_id', sa.Integer(), nullable=True))

    # Paso 2: backfill con usuario.unidad_id
    op.execute(f"""
        UPDATE {tabla}
        SET unidad_id = usuario.unidad_id
        FROM usuario
        WHERE {tabla}.usuario_id = usuario.id
          AND {tabla}.unidad_id IS NULL
    """)

    with op.batch_alter_table(tabla, schema=None) as batch_op:
        # Paso 3: NOT NULL
        batch_op.alter_column('unidad_id', nullable=False)
        batch_op.create_foreign_key(fk_name, 'unidad', ['unidad_id'], ['id'])
        batch_op.create_unique_constraint(new_constraint, columnas)


def _downgrade_tabla(tabla, old_constraint, new_constraint, columnas, fk_name):
    with op.batch_alter_table(tabla, schema=None) as batch_op:
        batch_op.drop_constraint(fk_name, type_='foreignkey')
        batch_op.drop_constraint(new_constraint, type_='unique')
        batch_op.create_unique_constraint(old_constraint, columnas)
        batch_op.drop_column('unidad_id')
