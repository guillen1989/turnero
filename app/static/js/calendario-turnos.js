/**
 * Widget de calendario tap-to-select para publicar turnos.
 *
 * Sustituye las filas manuales "fecha + tipo de turno" por: elegir una
 * franja (chip) y tocar los días del mes en los que se cede/acepta ese
 * turno. Genera los mismos inputs ocultos fecha_{prefix}_N / franja_{prefix}_N
 * que consumía el formulario anterior (app/routes/publicaciones.py::_extraer_turnos),
 * así que el backend no cambia.
 */
(function (global) {
  'use strict';

  var DIAS_ES = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
  var MESES_ES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
  ];

  function pad2(n) { return n < 10 ? '0' + n : String(n); }

  function CalendarioTurnos(container, opciones) {
    this.container = container;
    this.prefix = opciones.prefix;
    this.franjas = (opciones.franjas || []).map(function (f) {
      return { id: String(f.id), nombre: f.nombre, horario: f.horario, color: f.color, colorTexto: f.colorTexto };
    });
    if (opciones.incluirCualquiera) {
      this.franjas.unshift({
        id: '0', nombre: opciones.textoCualquiera, horario: '',
        color: '#94a3b8', colorTexto: '#ffffff',
      });
    }
    this.textos = opciones.textos || {};

    var hoyParts = opciones.today.split('-').map(Number);
    this.hoyY = hoyParts[0]; this.hoyM = hoyParts[1] - 1; this.hoyD = hoyParts[2];
    this.hoyIso = opciones.today;

    this.prefillFecha = opciones.prefillFecha || null;

    this.selection = {}; // { 'YYYY-MM-DD': ['franjaId', ...] }
    (opciones.seleccionInicial || []).forEach(function (par) {
      var iso = par[0];
      var fid = String(par[1]);
      var arr = this.selection[iso] || [];
      if (arr.indexOf(fid) < 0) arr = arr.concat([fid]);
      this.selection[iso] = arr;
    }, this);

    var fechaVista = this.prefillFecha;
    if (!fechaVista) {
      var fechasSeleccion = Object.keys(this.selection).sort();
      if (fechasSeleccion.length) fechaVista = fechasSeleccion[0];
    }
    if (fechaVista) {
      var p = fechaVista.split('-').map(Number);
      this.viewY = p[0]; this.viewM = p[1] - 1;
    } else {
      this.viewY = this.hoyY; this.viewM = this.hoyM;
    }

    this.activeFranjaId = this.franjas.length ? this.franjas[0].id : null;

    this._construir();
    this.render();
  }

  CalendarioTurnos.prototype._construir = function () {
    this.container.innerHTML =
      '<div class="cal-turnos-franjas" data-role="franjas"></div>' +
      '<div class="cal-turnos-nav">' +
        '<button type="button" class="btn btn-secondary btn-sm" data-role="prev">&lsaquo;</button>' +
        '<span class="cal-turnos-mes" data-role="mes-label"></span>' +
        '<button type="button" class="btn btn-secondary btn-sm" data-role="next">&rsaquo;</button>' +
      '</div>' +
      '<div class="planilla-cal cal-turnos-grid" data-role="grid"></div>' +
      '<p class="cal-turnos-resumen-count" data-role="resumen-count"></p>' +
      '<div class="cal-turnos-resumen" data-role="resumen"></div>' +
      '<div data-role="inputs"></div>';

    this.elFranjas = this.container.querySelector('[data-role="franjas"]');
    this.elPrev = this.container.querySelector('[data-role="prev"]');
    this.elNext = this.container.querySelector('[data-role="next"]');
    this.elMesLabel = this.container.querySelector('[data-role="mes-label"]');
    this.elGrid = this.container.querySelector('[data-role="grid"]');
    this.elResumenCount = this.container.querySelector('[data-role="resumen-count"]');
    this.elResumen = this.container.querySelector('[data-role="resumen"]');
    this.elInputs = this.container.querySelector('[data-role="inputs"]');

    var self = this;
    this.elPrev.addEventListener('click', function () { self._cambiarMes(-1); });
    this.elNext.addEventListener('click', function () { self._cambiarMes(1); });
    this.elResumen.addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-quitar-fecha]');
      if (!btn) return;
      self._quitar(btn.dataset.quitarFecha, btn.dataset.quitarFranja);
    });
  };

  CalendarioTurnos.prototype._cambiarMes = function (delta) {
    var destino = this.viewY * 12 + this.viewM + delta;
    var minimo = this.hoyY * 12 + this.hoyM;
    if (destino < minimo) return;
    this.viewY = Math.floor(destino / 12);
    this.viewM = destino % 12;
    this.render();
  };

  CalendarioTurnos.prototype._esPasado = function (iso) {
    return iso < this.hoyIso;
  };

  CalendarioTurnos.prototype._toggleDia = function (iso) {
    if (this._esPasado(iso) || this.activeFranjaId === null) return;
    var arr = this.selection[iso] || [];
    var idx = arr.indexOf(this.activeFranjaId);
    if (idx >= 0) {
      arr.splice(idx, 1);
    } else {
      arr = arr.concat([this.activeFranjaId]);
    }
    if (arr.length) this.selection[iso] = arr; else delete this.selection[iso];
    this.render();
  };

  CalendarioTurnos.prototype._quitar = function (iso, franjaId) {
    var arr = this.selection[iso] || [];
    var idx = arr.indexOf(franjaId);
    if (idx >= 0) arr.splice(idx, 1);
    if (arr.length) this.selection[iso] = arr; else delete this.selection[iso];
    this.render();
  };

  CalendarioTurnos.prototype._franjaPorId = function (id) {
    for (var i = 0; i < this.franjas.length; i++) {
      if (this.franjas[i].id === id) return this.franjas[i];
    }
    return null;
  };

  CalendarioTurnos.prototype._renderFranjas = function () {
    var self = this;
    this.elFranjas.innerHTML = this.franjas.map(function (f) {
      var activa = f.id === self.activeFranjaId;
      return (
        '<button type="button" class="cal-turnos-chip' + (activa ? ' is-active' : '') + '"' +
        ' data-franja-id="' + f.id + '" data-franja-nombre="' + f.nombre + '"' +
        ' style="--chip-color:' + f.color + '" aria-pressed="' + activa + '">' +
        '<span class="cal-turnos-chip-nombre">' + f.nombre + '</span>' +
        (f.horario ? '<span class="cal-turnos-chip-horario">' + f.horario + '</span>' : '') +
        '</button>'
      );
    }).join('');
    this.elFranjas.querySelectorAll('button[data-franja-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        self.activeFranjaId = btn.dataset.franjaId;
        self.render();
      });
    });
  };

  CalendarioTurnos.prototype._renderNav = function () {
    this.elMesLabel.textContent = MESES_ES[this.viewM] + ' ' + this.viewY;
    this.elPrev.disabled = (this.viewY === this.hoyY && this.viewM === this.hoyM);
  };

  CalendarioTurnos.prototype._renderGrid = function () {
    var self = this;
    var primerDiaSemana = (new Date(this.viewY, this.viewM, 1).getDay() + 6) % 7; // 0=lunes
    var diasEnMes = new Date(this.viewY, this.viewM + 1, 0).getDate();
    var html = DIAS_ES.map(function (d) { return '<div class="cal-header">' + d + '</div>'; }).join('');

    for (var i = 0; i < primerDiaSemana; i++) {
      html += '<div class="cal-celda cal-celda--fuera" aria-hidden="true"></div>';
    }

    for (var dia = 1; dia <= diasEnMes; dia++) {
      var iso = this.viewY + '-' + pad2(this.viewM + 1) + '-' + pad2(dia);
      var pasado = this._esPasado(iso);
      var esHoy = iso === this.hoyIso;
      var esSugerida = this.prefillFecha === iso;
      var franjaIds = this.selection[iso] || [];

      var clases = ['cal-celda', 'cal-turnos-celda'];
      if (esHoy) clases.push('cal-celda--hoy');
      if (pasado) clases.push('cal-turnos-celda--pasado');
      if (esSugerida && !franjaIds.length) clases.push('cal-turnos-celda--sugerida');

      var estilo = '';
      var interior = '<span class="cal-num">' + dia + '</span>';
      if (franjaIds.length === 1) {
        var f = self._franjaPorId(franjaIds[0]);
        if (f) estilo = 'background:' + f.color + ';color:' + f.colorTexto + ';';
      } else if (franjaIds.length > 1) {
        interior += '<span class="cal-bandas-row">' + franjaIds.map(function (fid) {
          var fr = self._franjaPorId(fid);
          if (!fr) return '';
          var letra = fr.id === '0' ? '✦' : fr.nombre.charAt(0).toUpperCase();
          return '<span class="cal-banda" style="background:' + fr.color + ';color:' + fr.colorTexto + ';">' + letra + '</span>';
        }).join('') + '</span>';
      }

      html +=
        '<button type="button" class="' + clases.join(' ') + '"' +
        (pasado ? ' disabled' : '') +
        ' data-fecha="' + iso + '"' +
        (esSugerida ? ' data-sugerida="true"' : '') +
        ' aria-pressed="' + (franjaIds.length > 0) + '"' +
        (estilo ? ' style="' + estilo + '"' : '') +
        '>' + interior + '</button>';
    }

    this.elGrid.innerHTML = html;
    this.elGrid.querySelectorAll('button[data-fecha]:not(:disabled)').forEach(function (btn) {
      btn.addEventListener('click', function () { self._toggleDia(btn.dataset.fecha); });
    });
  };

  CalendarioTurnos.prototype._renderResumen = function () {
    var self = this;
    var total = 0;
    Object.keys(this.selection).forEach(function (iso) { total += self.selection[iso].length; });

    if (total === 0) {
      this.elResumenCount.textContent = '';
    } else {
      var palabra = total === 1 ? this.textos.turnoSing : this.textos.turnoPlur;
      this.elResumenCount.textContent = total + ' ' + palabra;
    }

    var porFranja = {};
    Object.keys(this.selection).sort().forEach(function (iso) {
      self.selection[iso].forEach(function (fid) {
        porFranja[fid] = porFranja[fid] || [];
        porFranja[fid].push(iso);
      });
    });

    this.elResumen.innerHTML = this.franjas
      .filter(function (f) { return porFranja[f.id]; })
      .map(function (f) {
        var chips = porFranja[f.id].map(function (iso) {
          var partes = iso.split('-');
          var etiqueta = partes[2] + '/' + partes[1];
          return (
            '<span class="cal-turnos-chip-fecha" style="background:' + f.color + ';color:' + f.colorTexto + ';">' +
            etiqueta +
            '<button type="button" data-quitar-fecha="' + iso + '" data-quitar-franja="' + f.id + '" aria-label="' + etiqueta + ' — ' + f.nombre + '">&times;</button>' +
            '</span>'
          );
        }).join('');
        return (
          '<div class="cal-turnos-grupo">' +
            '<span class="cal-turnos-grupo-titulo">' +
              '<span class="cal-turnos-dot" style="background:' + f.color + '"></span>' +
              f.nombre + (f.horario ? ' · ' + f.horario : '') +
            '</span>' +
            '<div class="cal-turnos-chips">' + chips + '</div>' +
          '</div>'
        );
      }).join('');
  };

  CalendarioTurnos.prototype._renderInputs = function () {
    var self = this;
    var pares = [];
    Object.keys(this.selection).sort().forEach(function (iso) {
      self.selection[iso].forEach(function (fid) { pares.push([iso, fid]); });
    });
    this.elInputs.innerHTML = pares.map(function (p, i) {
      return (
        '<input type="hidden" name="fecha_' + self.prefix + '_' + i + '" value="' + p[0] + '">' +
        '<input type="hidden" name="franja_' + self.prefix + '_' + i + '" value="' + p[1] + '">'
      );
    }).join('');
  };

  CalendarioTurnos.prototype.render = function () {
    this._renderFranjas();
    this._renderNav();
    this._renderGrid();
    this._renderResumen();
    this._renderInputs();
  };

  global.CalendarioTurnos = CalendarioTurnos;
})(window);
