// Cascade hospital → unidad dropdown
// Requires: #hospital-input, #unidad-input, #unidades-hint
// On hospital change, fetches /auth/api/unidades?hospital=... and updates a datalist (#unidades-datalist)

(function () {
  var hospitalInput = document.getElementById('hospital-input');
  var unidadInput = document.getElementById('unidad-input');
  var datalist = document.getElementById('unidades-datalist');

  if (!hospitalInput || !unidadInput || !datalist) return;

  var lastHospital = '';

  function cargarUnidades(hospitalNombre) {
    if (!hospitalNombre || hospitalNombre === lastHospital) return;
    lastHospital = hospitalNombre;
    fetch('/auth/api/unidades?hospital=' + encodeURIComponent(hospitalNombre))
      .then(function (r) { return r.json(); })
      .then(function (nombres) {
        datalist.innerHTML = '';
        nombres.forEach(function (n) {
          var opt = document.createElement('option');
          opt.value = n;
          datalist.appendChild(opt);
        });
        // Si solo hay una unidad, preseleccionarla si el campo está vacío
        if (nombres.length === 1 && !unidadInput.value) {
          unidadInput.value = nombres[0];
        }
      })
      .catch(function () {});
  }

  hospitalInput.addEventListener('change', function () {
    cargarUnidades(this.value.trim());
  });

  hospitalInput.addEventListener('blur', function () {
    cargarUnidades(this.value.trim());
  });

  // Cargar al inicio si ya hay valor (p. ej. página de perfil pre-rellenada)
  if (hospitalInput.value.trim()) {
    cargarUnidades(hospitalInput.value.trim());
  }
})();
