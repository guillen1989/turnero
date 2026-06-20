from app import create_app
from sqlalchemy import text
from app.extensions import db
from app.models import insertar_categorias_semilla, Categoria, Usuario
from app.services.registro import encontrar_o_crear_hospital, encontrar_o_crear_unidad

app = create_app()
with app.app_context():
    db.session.execute(text(
        "TRUNCATE notificacion, match_participacion, match_cambio, "
        "turno_cedido, turno_aceptado, publicacion_cambio, usuario, "
        "franja_horaria, unidad, grupo_intercambio, hospital, categoria "
        "RESTART IDENTITY CASCADE"
    ))
    db.session.commit()
    print("Datos borrados.")
    insertar_categorias_semilla()
    hospital = encontrar_o_crear_hospital("Sistema")
    unidad = encontrar_o_crear_unidad("Administracion", hospital)
    cat = Categoria(nombre="Administrador")
    db.session.add(cat)
    db.session.flush()
    admin = Usuario(
        nombre="admin",
        email="guillen@delbarrioblanco.net",
        unidad=unidad,
        categoria=cat,
        es_admin=True,
    )
    admin.set_password("relajate")
    db.session.add(admin)
    db.session.commit()
    print("Admin creado: guillen@delbarrioblanco.net")
