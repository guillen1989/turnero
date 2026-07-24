(function () {
  function poblar(select, placeholder, opciones, valorPrevio) {
    select.innerHTML = '';
    select.appendChild(new Option(placeholder.text, placeholder.value));
    opciones.forEach(function (o) {
      select.appendChild(new Option(o.text, o.value));
    });
    if (opciones.some(function (o) { return String(o.value) === valorPrevio; })) {
      select.value = valorPrevio;
    }
  }

  function initFiltroTurno(select, getUsuarioId, getFecha) {
    var opcionesOriginales = Array.prototype.map.call(select.options, function (o) {
      return { value: o.value, text: o.textContent };
    });
    var placeholder = opcionesOriginales[0];
    var completas = opcionesOriginales.slice(1);

    return function actualizar() {
      var usuarioId = getUsuarioId();
      var fecha = getFecha();
      if (!usuarioId || !fecha) return;
      var valorPrevio = select.value;
      fetch(
        '/documentos-cambio/api/turnos-disponibles?usuario_id=' + encodeURIComponent(usuarioId) +
        '&fecha=' + encodeURIComponent(fecha)
      )
        .then(function (r) { return r.json(); })
        .then(function (franjas) {
          if (!franjas || franjas.length === 0) {
            poblar(select, placeholder, completas, valorPrevio);
          } else {
            var opciones = franjas.map(function (f) { return { value: String(f.id), text: f.nombre }; });
            poblar(select, placeholder, opciones, valorPrevio);
          }
        })
        .catch(function () { poblar(select, placeholder, completas, valorPrevio); });
    };
  }

  window.initFiltroTurno = initFiltroTurno;
})();
