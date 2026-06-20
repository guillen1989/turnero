from datetime import time

import click

from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("seed-franjas")
def seed_franjas():
    """Siembra Mañana/Tarde/Noche en grupos que todavía no tienen franjas."""
    from app.models import GrupoIntercambio, FranjaHoraria

    franjas_default = [
        ("Mañana", time(7, 0), time(15, 0)),
        ("Tarde", time(15, 0), time(23, 0)),
        ("Noche", time(23, 0), time(7, 0)),
    ]

    grupos = GrupoIntercambio.query.all()
    seeded = 0
    for grupo in grupos:
        if grupo.franjas_horarias.count() == 0:
            for nombre, inicio, fin in franjas_default:
                db.session.add(FranjaHoraria(
                    nombre=nombre, hora_inicio=inicio, hora_fin=fin,
                    grupo_intercambio=grupo,
                ))
            seeded += 1
    db.session.commit()
    click.echo(f"Franjas sembradas en {seeded} grupo(s).")


if __name__ == "__main__":
    app.run()
