function(el, x, data) {
  var map = this;
  var cont = map.getContainer();
  var fichas = data.fichas;
  var ids = data.ids;
  var nombres = data.nombres;
  /* ---- Buscador: lógica pura -------------------------------------------
     Entre los marcadores PURO no hay nada que toque el DOM ni Leaflet, para que
     tests/probar_buscador.py pueda extraer el bloque y correrlo en Node
     sin navegador y sin render. No agregar acá nada que use `document`. */
  /* --BEGIN-PURO-- */
  function normalizar(txt) {
    return String(txt == null ? "" : txt)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  /* Devuelve la función de filtrado para un índice dado. Se normaliza una sola
     vez, al construirla, y no en cada tecla. */
  function hacerFiltro(items) {
    var MAX = 8, MIN = 2;
    var pre = items.map(function (it) {
      return { it: it, nombreN: normalizar(it.nombre), comunaN: normalizar(it.comuna) };
    });
    return function (consulta) {
      var q = String(consulta == null ? "" : consulta).trim();
      if (q.length < MIN) return [];
      var hits;
      if (/^[0-9]+$/.test(q)) {
        hits = pre.filter(function (p) { return String(p.it.rbd).indexOf(q) === 0; });
        hits.sort(function (a, b) { return Number(a.it.rbd) - Number(b.it.rbd); });
      } else {
        var qn = normalizar(q);
        hits = pre.filter(function (p) {
          return p.nombreN.indexOf(qn) !== -1 || p.comunaN.indexOf(qn) !== -1;
        });
        /* Primero los que coinciden al inicio del nombre; dentro de cada grupo,
           alfabético. Así escribir «escuela r» no entierra a «Escuela Reloca». */
        hits.sort(function (a, b) {
          var ai = a.nombreN.indexOf(qn) === 0 ? 0 : 1;
          var bi = b.nombreN.indexOf(qn) === 0 ? 0 : 1;
          if (ai !== bi) return ai - bi;
          return a.nombreN < b.nombreN ? -1 : (a.nombreN > b.nombreN ? 1 : 0);
        });
      }
      return hits.slice(0, MAX).map(function (p) { return p.it; });
    };
  }
  /* --END-PURO-- */

  var ESTILO_BASE = { weight: 1.2, color: "#ffffff" };
  var ESTILO_SEL = { weight: 3.5, color: "#0e3a47" };
  var actual = null;

  /* ---- Mapa base con respaldo ------------------------------------------
     Si las teselas principales fallan, se cambia a un segundo estilo del mismo
     proveedor. Si tampoco cargan, se avisa y los puntos siguen en su posición. */
  var teselas = [];
  map.eachLayer(function (l) { if (l instanceof L.TileLayer) teselas.push(l); });
  var base = teselas[0];
  function avisoSinBase() {
    var d = document.createElement("div");
    d.className = "aviso-base";
    d.textContent = "No se pudo cargar el mapa base. Los puntos mantienen su ubicación.";
    cont.appendChild(d);
  }
  if (base) {
    var fallos = 0, etapa = 0;
    base.on("tileerror", function () {
      fallos++;
      if (fallos >= 3 && etapa === 0) {
        etapa = 1; fallos = 0;
        map.removeLayer(base);
        var alt = L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
          { attribution: "Tiles &copy; Esri", maxZoom: 19 }
        ).addTo(map);
        alt.bringToBack();
        alt.on("tileerror", function () {
          fallos++;
          if (fallos >= 3 && etapa === 1) { etapa = 2; avisoSinBase(); }
        });
      }
    });
  }

  /* ---- Panel lateral ---------------------------------------------------- */
  var panel = document.createElement("aside");
  panel.className = "ficha-panel";
  panel.setAttribute("aria-label", "Ficha del establecimiento");
  panel.setAttribute("aria-hidden", "true");
  panel.innerHTML =
    '<button type="button" class="ficha-cerrar" aria-label="Cerrar ficha">&times;</button>' +
    '<div class="ficha-cuerpo" tabindex="-1"></div>';
  cont.appendChild(panel);
  L.DomEvent.disableClickPropagation(panel);
  L.DomEvent.disableScrollPropagation(panel);

  var cuerpo = panel.querySelector(".ficha-cuerpo");
  var cerrar = panel.querySelector(".ficha-cerrar");

  function esMovil() { return window.matchMedia("(max-width: 700px)").matches; }

  function cerrarFicha(devolverFoco) {
    panel.classList.remove("abierta");
    cont.classList.remove("panel-abierto");
    panel.setAttribute("aria-hidden", "true");
    if (actual) {
      actual.setStyle(ESTILO_BASE);
      var el2 = actual.getElement && actual.getElement();
      if (devolverFoco && el2) el2.focus({ preventScroll: true });
      actual = null;
    }
  }

  /* Desplaza el mapa para que el punto elegido no quede bajo el panel */
  function reencuadrar(layer) {
    var tam = map.getSize();
    var p = map.latLngToContainerPoint(layer.getLatLng());
    if (esMovil()) {
      var libre = tam.y * 0.36;
      if (p.y > libre - 24 || p.y < 24) map.panBy([0, p.y - libre / 2], { animate: true });
    } else {
      var libreX = tam.x - 396;
      if (p.x > libreX - 40 || p.x < 40) map.panBy([p.x - libreX / 2, 0], { animate: true });
    }
  }

  function abrir(layer, i) {
    if (actual && actual !== layer) actual.setStyle(ESTILO_BASE);
    actual = layer;
    layer.setStyle(ESTILO_SEL);
    layer.bringToFront();
    cuerpo.innerHTML = fichas[i];
    cuerpo.scrollTop = 0;
    panel.classList.add("abierta");
    cont.classList.add("panel-abierto");
    panel.setAttribute("aria-hidden", "false");
    cuerpo.focus({ preventScroll: true });
    reencuadrar(layer);
  }

  cerrar.addEventListener("click", function () { cerrarFicha(true); });
  document.addEventListener("keydown", function (e) {
    /* preventDefault marca que este Esc ya cerró la ficha, para que el mismo
       toque no saque además de la pantalla completa (ver más abajo). */
    if (e.key === "Escape" && panel.classList.contains("abierta")) {
      e.preventDefault();
      cerrarFicha(true);
    }
  });

  /* ---- Enlazar cada punto con su ficha ---------------------------------- */
  ids.forEach(function (id, i) {
    var layer = map.layerManager.getLayer("marker", id);
    if (!layer) return;
    layer.on("click", function () { abrir(layer, i); });
    try {
      var nodo = layer.getElement();
      if (nodo) {
        nodo.setAttribute("tabindex", "0");
        nodo.setAttribute("role", "button");
        nodo.setAttribute("aria-label", "Ver ficha de " + nombres[i]);
        nodo.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(layer, i); }
        });
      }
    } catch (err) { /* sin acceso al elemento: el clic sigue funcionando */ }
  });

  /* ---- Barra de búsqueda ------------------------------------------------
     Localiza, no filtra: elegir un resultado abre su ficha y encuadra el punto,
     sin ocultar los demás. Vive dentro del contenedor de Leaflet para no chocar
     con los controles del mapa, y se inserta como primer hijo para que Tab
     llegue al campo antes que a los 72 puntos. */
  var B = data.busqueda || {};
  var items = [];
  if (B.nombre) {
    for (var bi = 0; bi < B.nombre.length; bi++) {
      items.push({
        nombre: B.nombre[bi],
        comuna: B.comuna[bi],
        rbd: String(B.rbd[bi] == null ? "" : B.rbd[bi]),
        idx: String(B.idx[bi] == null ? "" : B.idx[bi]),
        enMapa: !!B.enMapa[bi]
      });
    }
  }
  var filtrar = hacerFiltro(items);
  var posPorIdx = {};
  ids.forEach(function (id, i) { posPorIdx[String(id)] = i; });

  var buscador = document.createElement("div");
  buscador.className = "buscador";
  buscador.innerHTML =
    '<input type="search" class="buscador-campo" id="buscador-campo"' +
    ' role="combobox" aria-expanded="false" aria-controls="buscador-lista"' +
    ' aria-autocomplete="list" autocomplete="off" spellcheck="false"' +
    ' placeholder="Buscar por nombre o RBD"' +
    ' aria-label="Buscar un establecimiento por nombre o RBD">' +
    '<ul class="buscador-lista" id="buscador-lista" role="listbox" hidden></ul>';
  cont.insertBefore(buscador, cont.firstChild);
  L.DomEvent.disableClickPropagation(buscador);
  L.DomEvent.disableScrollPropagation(buscador);

  var campo = buscador.querySelector(".buscador-campo");
  var lista = buscador.querySelector(".buscador-lista");
  var resultados = [];
  var resaltado = -1;

  function cerrarLista() {
    lista.hidden = true;
    lista.innerHTML = "";
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
    resultados = [];
    resaltado = -1;
  }

  function pintarResaltado() {
    var ops = lista.querySelectorAll('[role="option"]');
    for (var i = 0; i < ops.length; i++) {
      var on = (i === resaltado);
      if (on) { ops[i].classList.add("resaltado"); } else { ops[i].classList.remove("resaltado"); }
      ops[i].setAttribute("aria-selected", on ? "true" : "false");
    }
    if (resaltado >= 0 && ops[resaltado]) {
      campo.setAttribute("aria-activedescendant", ops[resaltado].id);
      if (ops[resaltado].scrollIntoView) ops[resaltado].scrollIntoView({ block: "nearest" });
    } else {
      campo.removeAttribute("aria-activedescendant");
    }
  }

  function pintar(q) {
    resultados = filtrar(q);
    resaltado = -1;
    if (String(q).trim().length < 2) { cerrarLista(); return; }
    lista.innerHTML = "";
    if (!resultados.length) {
      var vacio = document.createElement("li");
      vacio.className = "buscador-vacio";
      vacio.textContent = "Sin coincidencias para «" + q + "»";
      lista.appendChild(vacio);
    } else {
      resultados.forEach(function (it, i) {
        var li = document.createElement("li");
        li.className = "buscador-op" + (it.enMapa ? "" : " sin-mapa");
        li.id = "buscador-op-" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        var nom = document.createElement("span");
        nom.className = "op-nombre";
        nom.textContent = it.nombre;
        var meta = document.createElement("span");
        meta.className = "op-meta";
        /* textContent y no innerHTML: el nombre viene de la base, no de acá. */
        meta.textContent = it.comuna +
          (it.rbd ? " · RBD " + it.rbd : "") +
          (it.enMapa ? "" : " · sin ubicación en el mapa");
        li.appendChild(nom);
        li.appendChild(meta);
        /* mousedown y no click: así el campo no pierde el foco antes de elegir. */
        li.addEventListener("mousedown", function (e) { e.preventDefault(); elegir(i); });
        lista.appendChild(li);
      });
    }
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
  }

  function elegir(i) {
    var it = resultados[i];
    if (!it) return;
    campo.value = it.nombre;
    cerrarLista();
    if (it.enMapa) {
      var layer = map.layerManager.getLayer("marker", it.idx);
      var pos = posPorIdx[it.idx];
      if (layer && pos !== undefined) {
        /* Centrar sin tocar el zoom: el resultado puede estar fuera de la vista
           y reencuadrar() solo corrige el punto que queda bajo el panel, no uno
           fuera de pantalla. Cambiar el zoom le movería el piso al usuario. */
        map.setView(layer.getLatLng(), map.getZoom(), { animate: true });
        abrir(layer, pos);   // abrir() hace el reencuadre bajo el panel
      }
    } else {
      if (panel.classList.contains("abierta")) cerrarFicha(false);
      /* La lista de sin ubicación está fuera del mapa: en pantalla completa no
         se vería, así que primero se sale. */
      salirPantallaCompleta();
      var det = document.querySelector("details.sin-ubicacion");
      if (det) {
        det.open = true;
        if (det.scrollIntoView) det.scrollIntoView({ behavior: "smooth", block: "start" });
        var sum = det.querySelector("summary");
        if (sum) sum.focus({ preventScroll: true });
      }
    }
  }

  campo.addEventListener("input", function () { pintar(campo.value); });
  campo.addEventListener("blur", function () { setTimeout(cerrarLista, 150); });
  campo.addEventListener("keydown", function (e) {
    var abierta = !lista.hidden && resultados.length > 0;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!abierta) return;
      e.preventDefault();
      var d = (e.key === "ArrowDown") ? 1 : -1;
      if (resaltado < 0) { resaltado = (d > 0) ? 0 : resultados.length - 1; }
      else { resaltado = (resaltado + d + resultados.length) % resultados.length; }
      pintarResaltado();
    } else if (e.key === "Enter") {
      if (abierta) { e.preventDefault(); elegir(resaltado >= 0 ? resaltado : 0); }
    } else if (e.key === "Escape") {
      /* La lista primero; si ya está cerrada, el manejador de document cierra
         la ficha. Por eso se detiene la propagación solo en el primer caso. */
      if (!lista.hidden) { e.stopPropagation(); cerrarLista(); }
    }
  });

  /* ---- Pantalla completa -------------------------------------------------
     Se agranda el contenedor de Leaflet y no la página: buscador, leyenda y
     ficha viven dentro de él, así que siguen funcionando. Donde el navegador no
     tiene la API (Safari en iPhone), se simula con position: fixed. */
  var ICONO_ENTRAR =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">' +
    '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="square"/></svg>';
  var ICONO_SALIR =
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">' +
    '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="square"/></svg>';

  var conApi = !!(cont.requestFullscreen || cont.webkitRequestFullscreen);
  var simulada = false;

  function elementoPantallaCompleta() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }
  function enPantallaCompleta() {
    return simulada || elementoPantallaCompleta() === cont;
  }

  var ctlPc = L.control({ position: "topleft" });
  var botonPc;
  ctlPc.onAdd = function () {
    var caja = L.DomUtil.create("div", "leaflet-bar leaflet-control control-pc");
    botonPc = L.DomUtil.create("button", "boton-pc", caja);
    botonPc.type = "button";
    L.DomEvent.disableClickPropagation(caja);
    L.DomEvent.on(botonPc, "click", alternarPantallaCompleta);
    return caja;
  };
  ctlPc.addTo(map);

  function pintarBotonPc() {
    var on = enPantallaCompleta();
    var txt = on ? "Salir de pantalla completa" : "Ver el mapa en pantalla completa";
    botonPc.innerHTML = on ? ICONO_SALIR : ICONO_ENTRAR;
    botonPc.setAttribute("aria-label", txt);
    botonPc.setAttribute("title", txt);
    botonPc.setAttribute("aria-pressed", on ? "true" : "false");
    cont.classList.toggle("en-pantalla-completa", on);
  }

  function trasCambio() {
    pintarBotonPc();
    /* Leaflet no se entera solo de que cambió el tamaño del contenedor */
    setTimeout(function () {
      map.invalidateSize();
      if (actual) reencuadrar(actual);
    }, 60);
  }

  function simular() {
    if (simulada || elementoPantallaCompleta() === cont) return;
    simulada = true;
    cont.classList.add("pantalla-completa-simulada");
    document.documentElement.classList.add("visor-sin-scroll");
    trasCambio();
  }

  function entrarPantallaCompleta() {
    if (!conApi) { simular(); return; }
    var p = cont.requestFullscreen ? cont.requestFullscreen() : cont.webkitRequestFullscreen();
    if (!p || !p.then) return;   // Safari antiguo: sin promesa, avisa por el evento
    /* Si el navegador lo rechaza (iframe sin permiso) o deja la petición colgada
       sin responder (algunos visores embebidos), se simula. */
    var respondio = false;
    p.then(function () { respondio = true; },
           function () { respondio = true; conApi = false; simular(); });
    setTimeout(function () { if (!respondio) simular(); }, 1000);
  }

  function salirPantallaCompleta() {
    if (simulada) {
      simulada = false;
      cont.classList.remove("pantalla-completa-simulada");
      document.documentElement.classList.remove("visor-sin-scroll");
      trasCambio();
    } else if (elementoPantallaCompleta() === cont) {
      if (document.exitFullscreen) document.exitFullscreen();
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    }
  }

  function alternarPantallaCompleta() {
    if (enPantallaCompleta()) salirPantallaCompleta(); else entrarPantallaCompleta();
  }

  function alCambiarApi() {
    /* Si la petición colgada se concede tarde, manda la real sobre la simulada */
    if (simulada && elementoPantallaCompleta() === cont) {
      simulada = false;
      cont.classList.remove("pantalla-completa-simulada");
      document.documentElement.classList.remove("visor-sin-scroll");
    }
    trasCambio();
  }
  document.addEventListener("fullscreenchange", alCambiarApi);
  document.addEventListener("webkitfullscreenchange", alCambiarApi);
  /* Con la API, Esc lo maneja el navegador. En la simulada hay que hacerlo acá,
     y solo si ese Esc no cerró antes la ficha o la lista del buscador. */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && simulada && !e.defaultPrevented) salirPantallaCompleta();
  });

  pintarBotonPc();
}
