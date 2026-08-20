// ============================================================
// ENCONTRANDO EL NUVIHOGAR - APP.JS COMPLETO Y A PRUEBA DE FALLOS
// ============================================================

"use strict";

const API_URL = "data/arriendos.json";
const INMUEBLES_POR_PAGINA = 12;

let inmuebles = [];
let resultadosActuales = [];
let paginaActual = 1;

let mapa = null;
let capaMarcadores = null;

let promedioGlobal = 0;
let limiteBaratoGlobal = 0;
let limiteCaroGlobal = 0;

let favoritos = JSON.parse(localStorage.getItem("mis_favoritos_arriendos")) || [];
let viendoSoloFavoritos = false;

const PALABRAS_PROHIBIDAS_FRONTEND = [
    "local", "locales", "oficina", "oficinas", "bodega", "bodegas", 
    "lote", "lotes", "consultorio", "consultorios", "edificio", "comercial"
];

document.addEventListener("DOMContentLoaded", () => {
    configurarEventos();
    inicializarMapa();
    cargarArriendos();
});

function inicializarMapa() {
    const contenedor = document.getElementById("mapa-inmuebles");
    if (!contenedor) return;

    mapa = L.map("mapa-inmuebles").setView([3.4516, -76.5320], 12);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(mapa);

    capaMarcadores = L.layerGroup().addTo(mapa);
}

function obtenerDatosColor(canon) {
    if (!canon || canon === 0 || promedioGlobal === 0) {
        return { color: "#95a5a6", borde: "#7f8c8d" };
    }
    if (canon <= limiteBaratoGlobal) {
        return { color: "#2ecc71", borde: "#27ae60" };
    }
    if (canon >= limiteCaroGlobal) {
        return { color: "#e74c3c", borde: "#c0392b" };
    }
    return { color: "#f39c12", borde: "#e67e22" };
}

function actualizarMapa() {
    if (!mapa || !capaMarcadores) return;
    capaMarcadores.clearLayers();

    const inmueblesMapeables = resultadosActuales.filter(i => Number(i.lat) && Number(i.lng));
    if (inmueblesMapeables.length === 0) return;

    let bounds = [];

    inmueblesMapeables.forEach(inmueble => {
        const lat = Number(inmueble.lat);
        const lng = Number(inmueble.lng);
        const canon = Number(inmueble.canon) || 0;

        const colorInfo = obtenerDatosColor(canon);

        const marcador = L.circleMarker([lat, lng], {
            radius: 8,
            fillColor: colorInfo.color,
            color: colorInfo.borde,
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85
        });

        const popupHTML = `
            <div style="font-family: 'Poppins', sans-serif; text-align: center;">
                <strong style="display: block; font-size: 15px; margin-bottom: 2px;">${precioCOP(canon)}</strong>
                <span style="display: block; font-size: 12px; color: #687b83; margin-bottom: 8px;">${limpiarCodificacion(inmueble.tipo_inmueble)}</span>
                <a href="javascript:void(0)" onclick="irATarjeta('${inmueble.id}')" style="display: inline-block; font-size: 12px; color: #ffffff; background-color: #7b2cbf; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 600;">Ir al inmueble →</a>
            </div>
        `;

        marcador.bindPopup(popupHTML);
        capaMarcadores.addLayer(marcador);
        bounds.push([lat, lng]);
    });

    if (bounds.length > 0) {
        mapa.fitBounds(bounds, { padding: [20, 20], maxZoom: 14 });
    }
}

window.irATarjeta = function(idInmueble) {
    const id = String(idInmueble);
    const index = resultadosActuales.findIndex(i => String(i.id) === id);
    
    if (index !== -1) {
        const paginaDestino = Math.floor(index / INMUEBLES_POR_PAGINA) + 1;
        
        if (paginaActual !== paginaDestino) {
            paginaActual = paginaDestino;
            mostrarInmuebles(); 
        }

        setTimeout(() => {
            const tarjetaElemento = document.getElementById(`card-${id}`);
            if (tarjetaElemento) {
                mapa.closePopup();
                tarjetaElemento.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                tarjetaElemento.classList.add('tarjeta-destacada');
                setTimeout(() => {
                    tarjetaElemento.classList.remove('tarjeta-destacada');
                }, 2000);
            }
        }, 150);
    }
};

async function cargarArriendos() {
    actualizarEstado("Conectando...");
    try {
        const respuesta = await fetch(API_URL + "?v=" + new Date().getTime(), { cache: "no-store" });
        if (!respuesta.ok) throw new Error(`Error HTTP ${respuesta.status}`);

        const datos = await respuesta.json();
        if (!Array.isArray(datos)) throw new Error("La API no devolvió una lista.");

        const datosNormalizados = datos.map(i => normalizarInmueble(i));
        
        inmuebles = removerDuplicados(datosNormalizados);

        actualizarEstado("API conectada");
        actualizarSelectores();
        aplicarFiltros();

    } catch (error) {
        actualizarEstado("Error de conexión");
    }
}

function removerDuplicados(lista) {
    const imagenesVistas = new Set();
    const urlsVistas = new Set();

    return lista.filter(inmueble => {
        const urlFoto = (inmueble.imagen_principal || "").trim().toLowerCase();
        const urlOriginal = (inmueble.url_original || "").trim().toLowerCase();
        
        const tieneFotoValida = urlFoto !== "" && !urlFoto.includes("unsplash");

        if (tieneFotoValida && imagenesVistas.has(urlFoto)) return false;
        if (urlOriginal !== "" && urlsVistas.has(urlOriginal)) return false;

        if (tieneFotoValida) imagenesVistas.add(urlFoto);
        if (urlOriginal !== "") urlsVistas.add(urlOriginal);

        return true;
    });
}

function normalizarInmueble(inmueble) {
    let canonNumerico = Number(inmueble.canon || 0);
    if (canonNumerico > 0 && canonNumerico < 10000) canonNumerico = canonNumerico * 1000;

    return {
        ...inmueble,
        id: String(inmueble.id),
        canon: isNaN(canonNumerico) ? 0 : canonNumerico,
        lat: inmueble.lat || null,
        lng: inmueble.lng || null,
        imagen_principal: (inmueble.imagen_principal || "").trim(),
        ciudad: limpiarCodificacion(inmueble.ciudad || inmueble.municipio),
        municipio: limpiarCodificacion(inmueble.municipio || inmueble.ciudad),
        barrio: limpiarCodificacion(inmueble.barrio),
        tipo_inmueble: limpiarCodificacion(inmueble.tipo_inmueble || inmueble.tipo || "Apartamento"),
        titulo: limpiarCodificacion(inmueble.titulo || "Inmueble en arriendo"),
    };
}

function limpiarCodificacion(valor) {
    if (valor === null || valor === undefined) return "";
    let resultado = String(valor);
    const reemplazos = {
        "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ",
        "Ã ": "Á", "Ã‰": "É", "Ã ": "Í", "Ã“": "Ó", "Ãš": "Ú", "Ã‘": "Ñ"
    };
    Object.keys(reemplazos).forEach(inc => { resultado = resultado.split(inc).join(reemplazos[inc]); });
    return resultado.trim();
}

function texto(valor) { return limpiarCodificacion(valor).toLowerCase().trim(); }
function valorTexto(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }
function establecerTexto(id, valor) { const el = document.getElementById(id); if (el) el.textContent = valor; }
function actualizarEstado(mensaje) { establecerTexto("estado", mensaje); }

function precioCOP(valor) {
    if (!valor || Number(valor) <= 0) return "Consultar";
    return `$${Number(valor).toLocaleString("es-CO", { maximumFractionDigits: 0 })}`;
}

function convertirBooleano(valor) { return (valor === true || valor === "true" || valor === "si"); }
function coincideBooleano(valor, filtro) {
    if (!filtro) return true;
    const booleano = convertirBooleano(valor);
    return filtro === "si" ? booleano : !booleano;
}

function configurarEventos() {
    const ids = ["filtro-ciudad", "filtro-tipo", "filtro-habitaciones", "filtro-banos", "filtro-precio-minimo", "filtro-precio-maximo", "filtro-parqueadero", "filtro-mascotas", "ordenar"];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", () => { paginaActual = 1; aplicarFiltros(); });
        if (el.tagName === "INPUT") el.addEventListener("input", () => { paginaActual = 1; aplicarFiltros(); });
    });

    window.limpiarFiltros = function() {
        ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = (id === "ordenar") ? "relevancia" : ""; });
        viendoSoloFavoritos = false;
        
        const btn = document.getElementById("btn-ver-favoritos");
        if (btn) { 
            btn.classList.remove("activo"); 
            const textoFav = document.getElementById("texto-btn-fav");
            const svgIcono = btn.querySelector("svg");
            if (textoFav) textoFav.textContent = "Mis Favoritos";
            if (svgIcono) svgIcono.setAttribute("fill", "none");
            btn.setAttribute("aria-pressed", "false");
        }
        paginaActual = 1; 
        aplicarFiltros();
    };

    const btnLimpiar = document.getElementById("limpiar-filtros");
    if (btnLimpiar) btnLimpiar.addEventListener("click", window.limpiarFiltros);

    const btnFavoritos = document.getElementById("btn-ver-favoritos");
    if (btnFavoritos) {
        btnFavoritos.addEventListener("click", () => {
            viendoSoloFavoritos = !viendoSoloFavoritos;
            btnFavoritos.classList.toggle("activo", viendoSoloFavoritos);
            
            const textoFav = document.getElementById("texto-btn-fav");
            const svgIcono = btnFavoritos.querySelector("svg");

            if (viendoSoloFavoritos) {
                if (textoFav) textoFav.textContent = "Viendo Favoritos";
                if (svgIcono) svgIcono.setAttribute("fill", "currentColor");
                btnFavoritos.setAttribute("aria-pressed", "true");
            } else {
                if (textoFav) textoFav.textContent = "Mis Favoritos";
                if (svgIcono) svgIcono.setAttribute("fill", "none");
                btnFavoritos.setAttribute("aria-pressed", "false");
            }

            paginaActual = 1;
            aplicarFiltros();
        });
    }
}

window.toggleFavorito = function(idInmueble, elementoBoton) {
    const id = String(idInmueble);
    const index = favoritos.indexOf(id);
    const icono = elementoBoton.querySelector('.corazon-icono');
    
    if (index === -1) {
        favoritos.push(id);
        elementoBoton.classList.add("activo");
        icono.innerHTML = "♥"; 
        elementoBoton.setAttribute("aria-label", "Quitar de favoritos");
        elementoBoton.setAttribute("aria-pressed", "true");
    } else {
        favoritos.splice(index, 1);
        elementoBoton.classList.remove("activo");
        icono.innerHTML = "♡"; 
        elementoBoton.setAttribute("aria-label", "Guardar en favoritos");
        elementoBoton.setAttribute("aria-pressed", "false");
        
        if (viendoSoloFavoritos) aplicarFiltros();
    }
    localStorage.setItem("mis_favoritos_arriendos", JSON.stringify(favoritos));
};

function obtenerValoresUnicos(campo) {
    return [...new Set(inmuebles.map(i => limpiarCodificacion(i[campo])).filter(v => v && v.trim() !== ""))].sort();
}

function llenarSelect(id, valores, textoInicial) {
    const select = document.getElementById(id);
    if (!select) return;
    const valorActual = select.value;
    select.innerHTML = `<option value="">${textoInicial}</option>`;
    valores.forEach(v => {
        const op = document.createElement("option");
        op.value = v; op.textContent = v;
        select.appendChild(op);
    });
    if (valores.includes(valorActual)) select.value = valorActual;
}

function actualizarSelectores() {
    llenarSelect("filtro-ciudad", obtenerValoresUnicos("ciudad"), "Todas las ciudades");
    llenarSelect("filtro-tipo", obtenerValoresUnicos("tipo_inmueble"), "Todos los tipos");
}

function esComercialFrontend(textoEvaluar) {
    const t = String(textoEvaluar).toLowerCase();
    return PALABRAS_PROHIBIDAS_FRONTEND.some(p => new RegExp(`\\b${p}\\b`, "i").test(t));
}

function aplicarFiltros() {
    const ciudad = texto(valorTexto("filtro-ciudad"));
    const tipo = texto(valorTexto("filtro-tipo"));
    const habitaciones = Number(valorTexto("filtro-habitaciones")) || 0;
    const banos = Number(valorTexto("filtro-banos")) || 0;
    const precioMin = Number(valorTexto("filtro-precio-minimo")) || 0;
    const precioMax = Number(valorTexto("filtro-precio-maximo")) || 0;
    const parqueadero = valorTexto("filtro-parqueadero");
    const mascotas = valorTexto("filtro-mascotas");

    resultadosActuales = inmuebles.filter(inmueble => {
        const canon = Number(inmueble.canon) || 0;
        const tituloCompleto = `${inmueble.titulo} ${inmueble.tipo_inmueble} ${inmueble.barrio}`;

        if (canon < 300000 || esComercialFrontend(tituloCompleto)) return false;
        if (viendoSoloFavoritos && !favoritos.includes(inmueble.id)) return false;
        if (ciudad && texto(inmueble.ciudad) !== ciudad && texto(inmueble.municipio) !== ciudad) return false;
        if (tipo && texto(inmueble.tipo_inmueble) !== tipo) return false;
        if (habitaciones && (Number(inmueble.habitaciones) || 0) < habitaciones) return false;
        if (banos && (Number(inmueble.banos) || 0) < banos) return false;
        if (precioMin && canon < precioMin) return false;
        if (precioMax && canon > precioMax) return false;
        if (!coincideBooleano(inmueble.parqueadero, parqueadero)) return false;
        if (!coincideBooleano(inmueble.acepta_mascotas || inmueble.mascotas, mascotas)) return false;

        return true;
    });

    ordenarResultados();
    actualizarEstadisticas();
    mostrarInmuebles();
    actualizarMapa();
}

function actualizarEstadisticas() {
    establecerTexto("estadistica-cantidad", resultadosActuales.length);
    const precios = resultadosActuales.map(i => Number(i.canon) || 0).filter(p => p > 0);
    if (!precios.length) {
        promedioGlobal = 0; limiteBaratoGlobal = 0; limiteCaroGlobal = 0;
        establecerTexto("estadistica-promedio", "$0");
        establecerTexto("estadistica-minimo", "$0");
        establecerTexto("estadistica-maximo", "$0");
    } else {
        promedioGlobal = precios.reduce((a, b) => a + b, 0) / precios.length;
        limiteBaratoGlobal = promedioGlobal * 0.85; limiteCaroGlobal = promedioGlobal * 1.15;
        establecerTexto("estadistica-promedio", precioCOP(promedioGlobal));
        establecerTexto("estadistica-minimo", precioCOP(Math.min(...precios)));
        establecerTexto("estadistica-maximo", precioCOP(Math.max(...precios)));
    }
}

function ordenarResultados() {
    const el = document.getElementById("ordenar");
    if (!el) return;
    const orden = el.value;
    resultadosActuales.sort((a, b) => {
        const pA = Number(a.canon) || 0, pB = Number(b.canon) || 0;
        switch (orden) {
            case "precio-menor": return pA - pB;
            case "precio-mayor": return pB - pA;
            case "area-mayor": return (Number(b.area_m2) || 0) - (Number(a.area_m2) || 0);
            default: return 0;
        }
    });
}

function mostrarInmuebles() {
    const lista = document.getElementById("lista-inmuebles");
    if (!lista) return;
    lista.innerHTML = "";

    // CONTROL DE ESTADO VACÍO (EMPTY STATE)
    if (resultadosActuales.length === 0) {
        lista.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h3>No encontramos resultados</h3>
                <p>Intenta ajustar los filtros, el rango de precio o la ciudad para ver más opciones.</p>
                <button onclick="window.limpiarFiltros()" class="btn-limpiar-empty">Quitar todos los filtros</button>
            </div>
        `;
        document.getElementById("paginacion").innerHTML = "";
        return;
    }

    const inicio = (paginaActual - 1) * INMUEBLES_POR_PAGINA;
    const pagina = resultadosActuales.slice(inicio, inicio + INMUEBLES_POR_PAGINA);
    pagina.forEach(inmueble => lista.appendChild(crearTarjeta(inmueble)));
    mostrarPaginacion();
}

function crearTarjeta(inmueble) {
    const tarjeta = document.createElement("article");
    tarjeta.className = "property-card";
    tarjeta.id = `card-${inmueble.id}`;

    const canon = Number(inmueble.canon) || 0;
    const colorInfo = obtenerDatosColor(canon);
    
    const usaImagenReferencia = !inmueble.imagen_principal || inmueble.imagen_principal === "";
    const imagenPorDefecto = 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?q=80&w=600&auto=format&fit=crop';
    const urlImagen = usaImagenReferencia ? imagenPorDefecto : inmueble.imagen_principal;
    
    const overlayHTML = usaImagenReferencia 
        ? `<div class="overlay-referencia"><span class="texto-ref">Imagen de ref.</span></div>` 
        : '';
    
    const esFavorito = favoritos.includes(inmueble.id);
    const iconoCorazon = esFavorito ? "♥" : "♡";
    const claseFavorito = esFavorito ? "btn-favorito activo" : "btn-favorito";
    const ariaLabel = esFavorito ? "Quitar de favoritos" : "Guardar en favoritos";
    
    // Alt Text Accesible para Lectores de Pantalla
    const altText = `Foto de ${limpiarCodificacion(inmueble.tipo_inmueble)} en ${limpiarCodificacion(inmueble.barrio)}`;

    tarjeta.innerHTML = `
        <div class="property-image">
            <img src="${urlImagen}" alt="${altText}" loading="lazy" onerror="this.onerror=null; this.src='${imagenPorDefecto}';">
            ${overlayHTML}
            <span class="property-type">${limpiarCodificacion(inmueble.tipo_inmueble)}</span>
            
            <button class="${claseFavorito}" onclick="toggleFavorito('${inmueble.id}', this)" aria-label="${ariaLabel}" aria-pressed="${esFavorito}" title="${ariaLabel}">
                <span class="corazon-icono">${iconoCorazon}</span>
            </button>
        </div>
        <div class="property-content">
            <div class="property-location"><span>${limpiarCodificacion(inmueble.barrio)} · ${limpiarCodificacion(inmueble.ciudad)}</span></div>
            <h3 class="property-price">
                <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background-color:${colorInfo.color}; margin-right:8px;"></span>
                ${precioCOP(canon)}
            </h3>
            <div class="property-details">
                <div><strong>${Number(inmueble.habitaciones) || "—"}</strong><span>habs</span></div>
                <div><strong>${Number(inmueble.banos) || "—"}</strong><span>baños</span></div>
                <div><strong>${Number(inmueble.area_m2) || "—"}</strong><span>m²</span></div>
            </div>
            <div class="property-footer">
                <a class="property-button" href="${inmueble.url_original || '#'}" target="_blank">Ver anuncio →</a>
            </div>
        </div>
    `;
    return tarjeta;
}

function mostrarPaginacion() {
    const contenedor = document.getElementById("paginacion");
    if (!contenedor) return;
    contenedor.innerHTML = "";
    
    const totalPaginas = Math.ceil(resultadosActuales.length / INMUEBLES_POR_PAGINA);
    if (totalPaginas <= 1) return;

    // CONTROL INTELIGENTE DE PAGINACIÓN (Máximo 5 botones + Flechas)
    
    const btnPrev = document.createElement("button");
    btnPrev.innerHTML = "&laquo;";
    btnPrev.className = "arrow-btn";
    btnPrev.title = "Página anterior";
    btnPrev.disabled = paginaActual === 1;
    btnPrev.onclick = () => { 
        if (paginaActual > 1) { 
            paginaActual--; mostrarInmuebles(); window.scrollTo({ top: 0, behavior: "smooth" }); 
        } 
    };
    contenedor.appendChild(btnPrev);

    let inicio = Math.max(1, paginaActual - 2);
    let fin = Math.min(totalPaginas, inicio + 4);
    
    if (fin - inicio < 4) {
        inicio = Math.max(1, fin - 4);
    }

    for (let p = inicio; p <= fin; p++) {
        const boton = document.createElement("button");
        boton.textContent = p;
        if (p === paginaActual) boton.classList.add("active");
        boton.addEventListener("click", () => { 
            paginaActual = p; mostrarInmuebles(); window.scrollTo({ top: 0, behavior: "smooth" }); 
        });
        contenedor.appendChild(boton);
    }

    const btnNext = document.createElement("button");
    btnNext.innerHTML = "&raquo;";
    btnNext.className = "arrow-btn";
    btnNext.title = "Página siguiente";
    btnNext.disabled = paginaActual === totalPaginas;
    btnNext.onclick = () => { 
        if (paginaActual < totalPaginas) { 
            paginaActual++; mostrarInmuebles(); window.scrollTo({ top: 0, behavior: "smooth" }); 
        } 
    };
    contenedor.appendChild(btnNext);
}