/**
 * Cascade geográfico: País → Provincia → Ciudad → Hospital → (Categoría) → Unidad
 *
 * IDs esperados en el DOM:
 *   #pais-select        #pais-nuevo-group
 *   #provincia-select   #provincia-nueva-group
 *   #ciudad-select      #ciudad-nueva-group
 *   #hospital-select    #hospital-nuevo-group
 *   #categoria-select   (opcional, filtra unidades)
 *   #unidad-select      #unidad-nuevo-group
 *
 * Cada select con "Añadir nuevo" usa value="0".
 * Los datos pre-seleccionados en perfil se leen de data-selected-* en cada select.
 */
(function () {
  var NUEVA = '0';

  function $(id) { return document.getElementById(id); }

  var paisSel      = $('pais-select');
  var provinciaSel = $('provincia-select');
  var ciudadSel    = $('ciudad-select');
  var hospitalSel  = $('hospital-select');
  var categoriaSel = $('categoria-select');
  var unidadSel    = $('unidad-select');

  // Sin el mínimo necesario, salir silenciosamente
  if (!paisSel && !hospitalSel) return;

  // ---------------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------------

  function mostrar(id, visible) {
    var el = $(id);
    if (el) el.style.display = visible ? '' : 'none';
  }

  function opcionNueva(label) {
    var o = document.createElement('option');
    o.value = NUEVA;
    o.textContent = label;
    return o;
  }

  function opcionPlaceholder(label) {
    var o = document.createElement('option');
    o.value = '';
    o.textContent = label;
    return o;
  }

  function poblarSelect(sel, lista, labelPlaceholder, labelNueva, selectedId, labelCount) {
    sel.innerHTML = '';
    sel.appendChild(opcionPlaceholder(labelPlaceholder));
    lista.forEach(function (item) {
      var o = document.createElement('option');
      o.value = item.id;
      o.textContent = (labelCount && item.count > 0)
        ? item.nombre + ' (' + item.count + ' ' + labelCount + ')'
        : item.nombre;
      if (String(item.id) === String(selectedId)) o.selected = true;
      sel.appendChild(o);
    });
    sel.appendChild(opcionNueva(labelNueva));
    // Si hay exactamente uno y no hay preselección, elegirlo
    if (!selectedId && lista.length === 1) sel.value = String(lista[0].id);
  }

  function limpiarSelect(sel, labelPlaceholder, labelNueva) {
    sel.innerHTML = '';
    sel.appendChild(opcionPlaceholder(labelPlaceholder));
    sel.appendChild(opcionNueva(labelNueva));
  }

  function fetchJSON(url, cb) {
    fetch(url).then(function (r) { return r.json(); }).then(cb).catch(function () { cb([]); });
  }

  // ---------------------------------------------------------------------------
  // Cascadas individuales
  // ---------------------------------------------------------------------------

  function toggleNuevoGrupo(selId, grupoId) {
    var sel = $(selId);
    if (sel) mostrar(grupoId, sel.value === NUEVA);
  }

  function cargarProvincias(paisId, selectedId) {
    if (!provinciaSel) return;
    if (!paisId || paisId === NUEVA) {
      limpiarSelect(provinciaSel, '— Selecciona provincia —', '— Añadir nueva provincia —');
      mostrar('provincia-nuevo-group', false);
      cargarCiudades(null, null);
      return;
    }
    fetchJSON('/auth/api/provincias?pais_id=' + paisId, function (lista) {
      poblarSelect(provinciaSel, lista, '— Selecciona provincia —', '— Añadir nueva provincia —', selectedId, 'ciudades');
      mostrar('provincia-nuevo-group', provinciaSel.value === NUEVA);
      cargarCiudades(
        (provinciaSel.value && provinciaSel.value !== NUEVA) ? provinciaSel.value : null,
        null,
      );
    });
  }

  function cargarCiudades(provinciaId, selectedId) {
    if (!ciudadSel) return;
    if (!provinciaId || provinciaId === NUEVA) {
      limpiarSelect(ciudadSel, '— Selecciona ciudad —', '— Añadir nueva ciudad —');
      mostrar('ciudad-nuevo-group', false);
      cargarHospitales(null, null);
      return;
    }
    fetchJSON('/auth/api/ciudades?provincia_id=' + provinciaId, function (lista) {
      poblarSelect(ciudadSel, lista, '— Selecciona ciudad —', '— Añadir nueva ciudad —', selectedId, 'hospitales');
      mostrar('ciudad-nuevo-group', ciudadSel.value === NUEVA);
      cargarHospitales(
        (ciudadSel.value && ciudadSel.value !== NUEVA) ? ciudadSel.value : null,
        null,
      );
    });
  }

  function cargarHospitales(ciudadId, selectedId) {
    if (!hospitalSel) return;
    if (!ciudadId || ciudadId === NUEVA) {
      limpiarSelect(hospitalSel, '— Selecciona hospital —', '— Añadir nuevo hospital —');
      mostrar('hospital-nuevo-group', false);
      cargarUnidades(null, null);
      return;
    }
    fetchJSON('/auth/api/hospitales?ciudad_id=' + ciudadId, function (lista) {
      poblarSelect(hospitalSel, lista, '— Selecciona hospital —', '— Añadir nuevo hospital —', selectedId, 'unidades');
      mostrar('hospital-nuevo-group', hospitalSel.value === NUEVA);
      cargarUnidades(
        (hospitalSel.value && hospitalSel.value !== NUEVA) ? hospitalSel.value : null,
        null,
      );
    });
  }

  function cargarUnidades(hospitalId, selectedId) {
    if (!unidadSel) return;
    if (!hospitalId || hospitalId === NUEVA) {
      limpiarSelect(unidadSel, '— Selecciona primero hospital y categoría —', '— Añadir nueva unidad —');
      mostrar('unidad-nuevo-group', false);
      return;
    }
    var catId = (categoriaSel && categoriaSel.value && categoriaSel.value !== NUEVA)
      ? '&categoria_id=' + categoriaSel.value : '';
    fetchJSON('/auth/api/unidades?hospital_id=' + hospitalId + catId, function (lista) {
      poblarSelect(unidadSel, lista, '— Selecciona unidad —', '— Añadir nueva unidad —', selectedId, 'usuarios');
      mostrar('unidad-nuevo-group', unidadSel.value === NUEVA);
    });
  }

  // ---------------------------------------------------------------------------
  // Listeners
  // ---------------------------------------------------------------------------

  if (paisSel) {
    paisSel.addEventListener('change', function () {
      mostrar('pais-nuevo-group', paisSel.value === NUEVA);
      cargarProvincias(paisSel.value, null);
    });
  }

  if (provinciaSel) {
    provinciaSel.addEventListener('change', function () {
      mostrar('provincia-nuevo-group', provinciaSel.value === NUEVA);
      cargarCiudades(provinciaSel.value, null);
    });
  }

  if (ciudadSel) {
    ciudadSel.addEventListener('change', function () {
      mostrar('ciudad-nuevo-group', ciudadSel.value === NUEVA);
      cargarHospitales(ciudadSel.value, null);
    });
  }

  if (hospitalSel) {
    hospitalSel.addEventListener('change', function () {
      mostrar('hospital-nuevo-group', hospitalSel.value === NUEVA);
      cargarUnidades(hospitalSel.value, null);
    });
  }

  if (categoriaSel) {
    categoriaSel.addEventListener('change', function () {
      var hId = hospitalSel ? hospitalSel.value : null;
      if (hId && hId !== NUEVA && hId !== '') cargarUnidades(hId, null);
    });
  }

  if (unidadSel) {
    unidadSel.addEventListener('change', function () {
      mostrar('unidad-nuevo-group', unidadSel.value === NUEVA);
    });
  }

  // ---------------------------------------------------------------------------
  // Estado inicial (perfil pre-rellenado via data-selected-*)
  // ---------------------------------------------------------------------------

  var initPaisId      = paisSel      ? (paisSel.dataset.selectedPais           || paisSel.value)      : null;
  var initProvinciaId = provinciaSel ? (provinciaSel.dataset.selectedProvincia || '')                  : null;
  var initCiudadId    = ciudadSel    ? (ciudadSel.dataset.selectedCiudad       || '')                  : null;
  var initHospitalId  = hospitalSel  ? (hospitalSel.dataset.selectedHospital   || hospitalSel.value)   : null;
  var initUnidadId    = unidadSel    ? (unidadSel.dataset.selectedUnidad       || '')                  : null;

  // Si hay pais seleccionado al cargar (perfil), disparar la cascada completa
  if (initPaisId && initPaisId !== NUEVA && initPaisId !== '') {
    mostrar('pais-nuevo-group', false);
    // Cargar provincias y dentro de esa callback cargar ciudades, luego hospitales, luego unidades
    if (provinciaSel) {
      fetchJSON('/auth/api/provincias?pais_id=' + initPaisId, function (lista) {
        poblarSelect(provinciaSel, lista, '— Selecciona provincia —', '— Añadir nueva provincia —', initProvinciaId, 'ciudades');
        mostrar('provincia-nuevo-group', provinciaSel.value === NUEVA);

        var provId = initProvinciaId || (lista.length === 1 ? String(lista[0].id) : null);
        if (provId && provId !== NUEVA && ciudadSel) {
          fetchJSON('/auth/api/ciudades?provincia_id=' + provId, function (lista2) {
            poblarSelect(ciudadSel, lista2, '— Selecciona ciudad —', '— Añadir nueva ciudad —', initCiudadId, 'hospitales');
            mostrar('ciudad-nuevo-group', ciudadSel.value === NUEVA);

            var civId = initCiudadId || (lista2.length === 1 ? String(lista2[0].id) : null);
            if (civId && civId !== NUEVA && hospitalSel) {
              fetchJSON('/auth/api/hospitales?ciudad_id=' + civId, function (lista3) {
                poblarSelect(hospitalSel, lista3, '— Selecciona hospital —', '— Añadir nuevo hospital —', initHospitalId, 'unidades');
                mostrar('hospital-nuevo-group', hospitalSel.value === NUEVA);

                var hId = initHospitalId || (lista3.length === 1 ? String(lista3[0].id) : null);
                if (hId && hId !== NUEVA && unidadSel) {
                  cargarUnidades(hId, initUnidadId);
                }
              });
            }
          });
        }
      });
    }
  } else if (initHospitalId && initHospitalId !== NUEVA && initHospitalId !== '') {
    // Compatibilidad: hospital ya seleccionado sin jerarquía geográfica (datos legacy)
    mostrar('hospital-nuevo-group', false);
    cargarUnidades(initHospitalId, initUnidadId);
  } else {
    // Nada seleccionado: mostrar grupos "nuevo" solo si el valor actual ya es NUEVA
    if (paisSel) mostrar('pais-nuevo-group', paisSel.value === NUEVA);
    if (hospitalSel) mostrar('hospital-nuevo-group', hospitalSel.value === NUEVA);
    if (unidadSel) mostrar('unidad-nuevo-group', unidadSel.value === NUEVA);
  }
})();
