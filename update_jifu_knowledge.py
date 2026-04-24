#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_jifu_knowledge.py
────────────────────────
Detecta transcripciones nuevas o modificadas y las agrega a
jifu_knowledge_base.md en la sección correcta según su carpeta y título.

Uso:
    python3 update_jifu_knowledge.py
"""

import os
import re
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

# ── Rutas absolutas ─────────────────────────────────────────────────────────
BASE_DIR = Path('/root/jifu-knowledge')
KB_PATH  = BASE_DIR / 'jifu_knowledge_base.md'
LOG_PATH = BASE_DIR / 'processed_files.log'

# ── Mapeo directo: carpeta → sección del knowledge base ─────────────────────
CARPETA_A_SECCION = {
    'guias-tecnicas':       'Guías Técnicas',
    'habilidades-ventas':   'Habilidades de Ventas',
    'liderazgo-vision':     'Liderazgo y Visión',
    'masterminds-talleres': 'Masterminds y Talleres',
    'pagos-cobros':         'Pagos y Cobros',
}

# Orden de aparición de secciones en el archivo final
ORDEN_SECCIONES = [
    'Guías Técnicas',
    'Habilidades de Ventas',
    'Liderazgo y Visión',
    'Masterminds y Talleres',
    'Pagos y Cobros',
    'Presentaciones de Negocio',
    'Testimonios',
    'Celebraciones y Reconocimientos',
    'Redes Sociales y Marketing',
    'Sin Categoría',
]

# Palabras clave para reclasificar archivos que vienen de sin-categoria.
# Se evalúan en orden: la primera coincidencia gana.
KEYWORDS_RECLASIFICACION = [
    ('Guías Técnicas', [
        'metatrader', 'mt5', 'instalar', 'vwap', 'tradingview',
        'wallet', 'cuenta demostrativa', 'jifu connect', 'taurex',
        'intensivo básico', 'curso intensivo', 'colocar operaciones',
        'nueva versión', 'broker', 'plataforma',
    ]),
    ('Presentaciones de Negocio', [
        'presentación de negocios', 'presentacion de negocios',
        'open house', 'latam', 'social trading', 'llamada de presentación',
    ]),
    ('Testimonios', [
        'testimonio', 'ecommerce',
    ]),
    ('Celebraciones y Reconocimientos', [
        'celebración', 'celebracion', 'lanzamiento', ' silver', ' gold',
        ' platinum', ' platino', ' elite', ' icon', 'zoom lily',
    ]),
    ('Redes Sociales y Marketing', [
        'redes sociales', 'salesads', 'ugc', 'masterclass de redes',
        'perfiles de redes', 'publicitario',
    ]),
    ('Liderazgo y Visión', [
        'misión épica', 'mision epica', '90 días', 'platino 2000',
        'alex morton', 'lograr rápido', 'super héroe', 'súper héroe',
        'avengers', 'network marketing',
    ]),
    ('Masterminds y Talleres', [
        'zoom ', 'zio', 'llamada con', 'masterclass social',
        'entrenamiento', 'bootcamp',
    ]),
]


# ── Utilidades ───────────────────────────────────────────────────────────────

def calcular_md5(ruta: Path) -> str:
    """Calcula el hash MD5 de un archivo para detectar cambios."""
    h = hashlib.md5()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(8192), b''):
            h.update(bloque)
    return h.hexdigest()


def cargar_log() -> dict:
    """Carga el log de archivos procesados. Devuelve {ruta_str: entrada}."""
    if not LOG_PATH.exists():
        return {}
    registro = {}
    with open(LOG_PATH, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    entrada = json.loads(linea)
                    registro[entrada['ruta']] = entrada
                except json.JSONDecodeError:
                    continue
    return registro


def guardar_entrada_log(entrada: dict):
    """Agrega una nueva entrada al log (append — nunca sobreescribe)."""
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + '\n')


# ── Parseo de transcripciones ────────────────────────────────────────────────

def parsear_transcripcion(ruta: Path) -> dict:
    """
    Lee un archivo .txt de transcripción y devuelve:
      - titulo: str
      - url: str
      - id_video: str
      - texto: str  (sin timestamps, agrupado en párrafos)
    """
    contenido = ruta.read_text(encoding='utf-8', errors='replace')
    lineas = contenido.splitlines()

    metadata = {'titulo': ruta.stem, 'url': '', 'id_video': ''}
    cuerpo = []
    en_cuerpo = False

    for linea in lineas:
        l = linea.strip()
        if not en_cuerpo:
            if l.startswith('Título:'):
                metadata['titulo'] = l[7:].strip()
            elif l.startswith('ID:'):
                metadata['id_video'] = l[3:].strip()
            elif l.startswith('URL:'):
                metadata['url'] = l[4:].strip()
            elif '=' * 10 in l:
                en_cuerpo = True
        else:
            if l:
                # Quitar timestamp [HH:MM] o [HH:MM:SS] del inicio
                texto_limpio = re.sub(r'^\[\d{1,2}:\d{2}(?::\d{2})?\]\s*', '', l)
                if texto_limpio:
                    cuerpo.append(texto_limpio)

    # Agrupar en párrafos de 6 líneas para legibilidad
    parrafos = []
    for i in range(0, len(cuerpo), 6):
        grupo = cuerpo[i:i + 6]
        parrafos.append(' '.join(grupo))

    metadata['texto'] = '\n\n'.join(parrafos)
    return metadata


# ── Clasificación ────────────────────────────────────────────────────────────

def detectar_seccion(carpeta: str, titulo: str) -> str:
    """
    Determina la sección del knowledge base para un archivo dado.
    - Si la carpeta está en el mapeo directo, lo usa.
    - Si viene de sin-categoria, analiza el título con keywords.
    - Fallback: 'Sin Categoría'
    """
    if carpeta in CARPETA_A_SECCION:
        return CARPETA_A_SECCION[carpeta]

    titulo_lower = titulo.lower()
    for seccion, keywords in KEYWORDS_RECLASIFICACION:
        if any(kw in titulo_lower for kw in keywords):
            return seccion

    return 'Sin Categoría'


# ── Gestión del knowledge base ───────────────────────────────────────────────

HEADER_KB = """\
# Base de Conocimiento JIFU
> Generado automáticamente por update_jifu_knowledge.py
> Última actualización: {fecha}

Este documento consolida el conocimiento extraído de {total} transcripciones
de videos de capacitación, presentaciones y talleres de JIFU Trading.

---
"""


def cargar_secciones_kb() -> dict:
    """
    Lee el KB y devuelve un dict {nombre_seccion: contenido_str}.
    La clave '__header__' guarda el bloque inicial antes de la primera sección.
    """
    if not KB_PATH.exists():
        return {}

    texto = KB_PATH.read_text(encoding='utf-8')

    # Separar por encabezados de sección (## Nombre)
    partes = re.split(r'\n(?=## )', texto)
    secciones = {}

    for parte in partes:
        if parte.startswith('## '):
            primera_linea, *resto = parte.split('\n', 1)
            nombre = primera_linea[3:].strip()
            secciones[nombre] = resto[0] if resto else ''
        else:
            secciones['__header__'] = parte

    return secciones


def guardar_kb(secciones: dict, total_archivos: int):
    """Reescribe el KB completo desde el dict de secciones."""
    partes = []

    # Encabezado del archivo
    partes.append(HEADER_KB.format(
        fecha=datetime.now().strftime('%Y-%m-%d %H:%M'),
        total=total_archivos,
    ).rstrip())

    # Secciones en orden definido
    for seccion in ORDEN_SECCIONES:
        if seccion in secciones:
            contenido = secciones[seccion].strip()
            partes.append(f'\n\n## {seccion}\n\n{contenido}')

    # Secciones fuera del orden (por si acaso)
    for seccion, contenido in secciones.items():
        if seccion not in ORDEN_SECCIONES and seccion != '__header__':
            partes.append(f'\n\n## {seccion}\n\n{contenido.strip()}')

    KB_PATH.write_text('\n'.join(partes) + '\n', encoding='utf-8')


def construir_entrada_md(meta: dict, archivo_fuente: str, seccion: str) -> str:
    """Construye el bloque Markdown para una transcripción."""
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
    url = meta.get('url', '')
    url_display = f'[Ver video]({url})' if url else '_sin URL_'

    bloque = (
        f"### {meta['titulo']}\n"
        f"> 📅 Procesado: {ahora} &nbsp;|&nbsp; "
        f"📄 Fuente: `{archivo_fuente}` &nbsp;|&nbsp; {url_display}\n\n"
        f"{meta['texto']}\n\n"
        f"---"
    )
    return bloque


# ── Pipeline principal ───────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('  JIFU Knowledge Base — Actualizador')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # Cargar historial de archivos ya procesados
    log = cargar_log()
    print(f'\n📋 Archivos previamente procesados: {len(log)}')

    # Escanear todas las carpetas de transcripciones
    carpetas = list(CARPETA_A_SECCION.keys()) + ['sin-categoria']
    archivos_pendientes = []

    for carpeta in carpetas:
        directorio = BASE_DIR / carpeta
        if not directorio.exists():
            continue
        for txt in sorted(directorio.glob('*.txt')):
            ruta_str = str(txt)
            md5_actual = calcular_md5(txt)
            entrada_log = log.get(ruta_str)

            if entrada_log and entrada_log.get('md5') == md5_actual:
                # Ya procesado y sin cambios — saltar
                continue

            motivo = 'modificado' if entrada_log else 'nuevo'
            archivos_pendientes.append((txt, carpeta, md5_actual, motivo))

    if not archivos_pendientes:
        print('\n✅ No hay transcripciones nuevas ni modificadas.')
        print('   El knowledge base está al día. No se realizó ningún trabajo.')
        sys.exit(0)

    print(f'\n🔍 Transcripciones pendientes: {len(archivos_pendientes)}')
    for ruta, carpeta, _, motivo in archivos_pendientes:
        print(f'   [{motivo:10s}] {carpeta}/{ruta.name}')

    # Cargar KB existente (o dict vacío si no existe)
    secciones_kb = cargar_secciones_kb()
    procesados_ok = []

    print('\n⚙️  Procesando...\n')

    for ruta, carpeta, md5_actual, motivo in archivos_pendientes:
        try:
            meta = parsear_transcripcion(ruta)
            seccion = detectar_seccion(carpeta, meta['titulo'])
            entrada_md = construir_entrada_md(meta, ruta.name, seccion)

            # Agregar al contenido de la sección en memoria
            contenido_actual = secciones_kb.get(seccion, '').strip()
            if contenido_actual:
                secciones_kb[seccion] = contenido_actual + '\n\n' + entrada_md
            else:
                secciones_kb[seccion] = entrada_md

            # Registrar en log
            nueva_entrada_log = {
                'archivo':            ruta.name,
                'ruta':               str(ruta),
                'bytes':              ruta.stat().st_size,
                'fecha_procesamiento': datetime.now().isoformat(timespec='seconds'),
                'seccion':            seccion,
                'md5':                md5_actual,
            }
            guardar_entrada_log(nueva_entrada_log)
            procesados_ok.append((ruta.name, seccion, motivo))

            print(f'   ✓ {ruta.name[:55]:<55} → {seccion}')

        except Exception as e:
            print(f'   ✗ ERROR en {ruta.name}: {e}')

    # Calcular total de archivos en el log actualizado
    total_en_log = len(cargar_log())

    # Guardar KB completo
    guardar_kb(secciones_kb, total_en_log)

    # Resumen final
    print('\n' + '=' * 60)
    print(f'  ✅ Completado: {len(procesados_ok)} transcripción(es) procesada(s)')
    print(f'  📚 KB guardado en: {KB_PATH}')
    print(f'  📊 Total en la base: {total_en_log} archivos')

    for nombre, seccion, motivo in procesados_ok:
        print(f'     • [{motivo}] {nombre} → {seccion}')

    kb_size = KB_PATH.stat().st_size / 1024
    print(f'\n  📄 Tamaño del KB: {kb_size:.1f} KB')
    print('=' * 60)


if __name__ == '__main__':
    main()
