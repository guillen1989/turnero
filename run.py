from datetime import time

import click

from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("seed-franjas")
def seed_franjas():
    """Siembra Mañana/Tarde/Noche en grupos que todavía no tienen franjas."""
    from app.models import GrupoIntercambio
    from app.services.registro import crear_franjas_default

    grupos = GrupoIntercambio.query.all()
    seeded = 0
    for grupo in grupos:
        if grupo.franjas_horarias.count() == 0:
            crear_franjas_default(grupo)
            seeded += 1
    db.session.commit()
    click.echo(f"Franjas sembradas en {seeded} grupo(s).")


if __name__ == "__main__":
    app.run()
