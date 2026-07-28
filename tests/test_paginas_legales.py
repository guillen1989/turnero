def test_privacidad_es_publica_y_devuelve_html(client):
    response = client.get("/privacidad")
    assert response.status_code == 200
    assert "text/html" in response.content_type


def test_terminos_es_publica_y_devuelve_html(client):
    response = client.get("/terminos")
    assert response.status_code == 200
    assert "text/html" in response.content_type


def test_eliminar_cuenta_es_publica_y_devuelve_html(client):
    response = client.get("/eliminar-cuenta")
    assert response.status_code == 200
    assert "text/html" in response.content_type
