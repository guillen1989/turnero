(function () {
  function setupFirmaCanvas(canvas) {
    var ctx = canvas.getContext('2d');
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#1a1a1a';
    var dibujando = false;
    var haFirmado = false;

    function pos(e) {
      var rect = canvas.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * (canvas.width / rect.width),
        y: (e.clientY - rect.top) * (canvas.height / rect.height),
      };
    }

    function empezar(e) {
      dibujando = true;
      haFirmado = true;
      var p = pos(e);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      canvas.setPointerCapture(e.pointerId);
      e.preventDefault();
    }
    function mover(e) {
      if (!dibujando) return;
      var p = pos(e);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      e.preventDefault();
    }
    function terminar() {
      dibujando = false;
    }

    canvas.addEventListener('pointerdown', empezar);
    canvas.addEventListener('pointermove', mover);
    canvas.addEventListener('pointerup', terminar);
    canvas.addEventListener('pointerleave', terminar);

    canvas._haFirmado = function () { return haFirmado; };
    canvas._limpiar = function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      haFirmado = false;
    };
  }

  function initFirmaForm(formId) {
    var form = document.getElementById(formId);
    if (!form) return;
    var canvas = form.querySelector('canvas.firma-canvas');
    var input = form.querySelector('input[name="imagen_firma"]');
    var btnLimpiar = form.querySelector('.firma-limpiar');
    var btnGuardada = form.querySelector('.firma-usar-guardada');

    setupFirmaCanvas(canvas);

    if (btnLimpiar) {
      btnLimpiar.addEventListener('click', function () {
        canvas._limpiar();
        input.value = '';
      });
    }

    if (btnGuardada) {
      btnGuardada.addEventListener('click', function () {
        input.value = btnGuardada.dataset.firma;
        if (form.requestSubmit) {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    }

    form.addEventListener('submit', function (e) {
      if (canvas._haFirmado()) {
        input.value = canvas.toDataURL('image/png');
      } else if (!input.value) {
        e.preventDefault();
        alert('Dibuja tu firma en el recuadro antes de guardar.');
      }
    });
  }

  function copiarAlPortapapeles(btn, texto) {
    navigator.clipboard.writeText(texto).then(function () {
      var original = btn.textContent;
      btn.textContent = btn.dataset.copiadoLabel || 'Copiado';
      setTimeout(function () { btn.textContent = original; }, 1500);
    });
  }

  window.initFirmaForm = initFirmaForm;
  window.copiarAlPortapapeles = copiarAlPortapapeles;
})();
