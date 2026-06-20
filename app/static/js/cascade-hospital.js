// Cascade hospital → unidad (select-based, como el de categorías)
// Requiere en el DOM: #hospital-select, #hospital-nuevo-group, #hospital-nuevo-input (opcional),
//                    #unidad-select, #unidad-nuevo-group, #unidad-nuevo-input (opcional)
// La API /auth/api/unidades?hospital_id=X devuelve [{id, nombre}, ...]

(function () {
  var hospitalSelect  = document.getElementById('hospital-select');
  var hospitalNuevoGroup = document.getElementById('hospital-nuevo-group');
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
    fetch('/auth/api/unidades?hospital_id=' + hospitalId)
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
