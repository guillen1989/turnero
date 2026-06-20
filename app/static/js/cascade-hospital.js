// Cascade hospital + categoria → unidad (select-based, como el de categorías)
// Requiere en el DOM: #hospital-select, #hospital-nuevo-group,
//                    #categoria-select (opcional, para filtrar unidades por categoría),
//                    #unidad-select, #unidad-nuevo-group
// La API /auth/api/unidades?hospital_id=X&categoria_id=Y devuelve [{id, nombre}, ...]

(function () {
  var hospitalSelect  = document.getElementById('hospital-select');
  var hospitalNuevoGroup = document.getElementById('hospital-nuevo-group');
  var categoriaSelect = document.getElementById('categoria-select');
  var unidadSelect    = document.getElementById('unidad-select');
  var unidadNuevoGroup = document.getElementById('unidad-nuevo-group');

  if (!hospitalSelect || !unidadSelect) return;

  var OPCION_NUEVA = '0';

  function mostrarGrupo(grupo, visible) {
    if (grupo) grupo.style.display = visible ? '' : 'none';
  }

  function toggleUnidadNuevo() {
    mostrarGrupo(unidadNuevoGroup, unidadSelect.value === OPCION_NUEVA);
  }

  function opcionNuevoUnidad(label) {
    var opt = document.createElement('option');
    opt.value = OPCION_NUEVA;
    opt.textContent = label || '— Añadir nueva unidad —';
    return opt;
  }

  function cargarUnidades(hospitalId, selectedUnidadId) {
    unidadSelect.innerHTML = '';
    if (!hospitalId || hospitalId === OPCION_NUEVA) {
      unidadSelect.appendChild(opcionNuevoUnidad());
      toggleUnidadNuevo();
      return;
    }
    var catId = (categoriaSelect && categoriaSelect.value && categoriaSelect.value !== OPCION_NUEVA)
      ? '&categoria_id=' + categoriaSelect.value : '';
    fetch('/auth/api/unidades?hospital_id=' + hospitalId + catId)
      .then(function (r) { return r.json(); })
      .then(function (lista) {
        var placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '— Selecciona unidad —';
        unidadSelect.appendChild(placeholder);

        lista.forEach(function (u) {
          var opt = document.createElement('option');
          opt.value = u.id;
          opt.textContent = u.nombre;
          if (String(u.id) === String(selectedUnidadId)) opt.selected = true;
          unidadSelect.appendChild(opt);
        });

        unidadSelect.appendChild(opcionNuevoUnidad());

        // Si ya había selección válida, restablecer; si solo hay una, preseleccionar
        if (!selectedUnidadId && lista.length === 1) {
          unidadSelect.value = lista[0].id;
        }
        toggleUnidadNuevo();
      })
      .catch(function () {
        unidadSelect.appendChild(opcionNuevoUnidad());
        toggleUnidadNuevo();
      });
  }

  function onHospitalChange() {
    var val = hospitalSelect.value;
    mostrarGrupo(hospitalNuevoGroup, val === OPCION_NUEVA);
    cargarUnidades(val, null);
  }

  hospitalSelect.addEventListener('change', onHospitalChange);
  unidadSelect.addEventListener('change', toggleUnidadNuevo);

  // Cuando cambia la categoría, recargar unidades
  if (categoriaSelect) {
    categoriaSelect.addEventListener('change', function () {
      var hId = hospitalSelect.value;
      if (hId && hId !== OPCION_NUEVA && hId !== '') {
        cargarUnidades(hId, null);
      }
    });
  }

  // Estado inicial (p. ej. perfil pre-rellenado: data-selected-unidad en el select)
  var initialHospitalId = hospitalSelect.value;
  var initialUnidadId   = unidadSelect.dataset.selectedUnidad || null;

  if (initialHospitalId && initialHospitalId !== OPCION_NUEVA && initialHospitalId !== '') {
    mostrarGrupo(hospitalNuevoGroup, false);
    cargarUnidades(initialHospitalId, initialUnidadId);
  } else {
    mostrarGrupo(hospitalNuevoGroup, initialHospitalId === OPCION_NUEVA);
    toggleUnidadNuevo();
  }
})();
