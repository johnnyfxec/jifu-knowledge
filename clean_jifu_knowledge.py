#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_jifu_knowledge.py
───────────────────────
Limpia y normaliza jifu_knowledge_base.md:
  - Aplica correcciones del archivo editable semantic_corrections.json
  - Elimina muletillas típicas de transcripciones automáticas
  - Crea backup con timestamp antes de modificar
  - Genera reporte de cambios realizados

Uso:
    python3 clean_jifu_knowledge.py
"""

import re
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

# ── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR     = Path('/root/jifu-knowledge')
KB_PATH      = BASE_DIR / 'jifu_knowledge_base.md'
CORREC_PATH  = BASE_DIR / 'semantic_corrections.json'
BACKUPS_DIR  = BASE_DIR / 'backups'


def crear_backup() -> Path:
    """Crea una copia de seguridad del KB con timestamp. Devuelve la ruta."""
    BACKUPS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    destino = BACKUPS_DIR / f'jifu_knowledge_base_backup_{timestamp}.md'
    shutil.copy2(KB_PATH, destino)
    return destino


def cargar_correcciones() -> dict:
    """Carga semantic_corrections.json. Devuelve el dict completo."""
    if not CORREC_PATH.exists():
        print(f'⚠️  No se encontró {CORREC_PATH.name} — se usarán solo correcciones internas.')
        return {'reemplazos': [], 'muletillas': []}
    with open(CORREC_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def aplicar_reemplazos(texto: str, reemplazos: list) -> tuple[str, list]:
    """
    Aplica reemplazos exactos de texto (case-sensitive).
    Devuelve (texto_modificado, lista_de_cambios).
    """
    cambios = []
    for item in reemplazos:
        origen  = item.get('de', '')
        destino = item.get('a', '')
        nota    = item.get('nota', '')
        if not origen or origen == destino:
            continue
        # Reemplazar solo si el texto resultante es diferente al patrón
        # (evita marcar como cambio cuando ya está correcto)
        nuevo_texto = texto.replace(origen, destino)
        conteo = texto.count(origen)
        if conteo > 0:
            cambios.append({
                'tipo':    'reemplazo',
                'de':      origen,
                'a':       destino,
                'conteo':  conteo,
                'nota':    nota,
            })
            texto = nuevo_texto
    return texto, cambios


def aplicar_muletillas(texto: str, patrones: list) -> tuple[str, list]:
    """
    Elimina muletillas usando expresiones regulares.
    Devuelve (texto_modificado, lista_de_cambios).
    """
    cambios = []
    for patron in patrones:
        try:
            nuevo_texto, conteo = re.subn(patron, ' ', texto, flags=re.IGNORECASE)
            if conteo > 0:
                cambios.append({
                    'tipo':   'muletilla',
                    'patron': patron,
                    'conteo': conteo,
                })
                texto = nuevo_texto
        except re.error as e:
            print(f'   ⚠️  Patrón inválido "{patron}": {e}')
    return texto, cambios


def limpiar_espacios_extra(texto: str) -> str:
    """Normaliza espacios múltiples dejados tras eliminar muletillas."""
    # Múltiples espacios → uno solo (sin tocar saltos de línea)
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    # Más de 2 líneas en blanco → 2 líneas en blanco
    texto = re.sub(r'\n{4,}', '\n\n\n', texto)
    return texto


def imprimir_reporte(cambios_reemplazos: list, cambios_muletillas: list, backup_path: Path):
    """Imprime el reporte de cambios en terminal."""
    total = sum(c['conteo'] for c in cambios_reemplazos + cambios_muletillas)

    print(f'\n📋 Reporte de limpieza — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('─' * 55)

    if cambios_reemplazos:
        print(f'\n🔤 Correcciones de texto ({len(cambios_reemplazos)} reglas activas):')
        for c in cambios_reemplazos:
            nota = f'  ← {c["nota"]}' if c.get('nota') else ''
            print(f'   {c["conteo"]:>4}x  "{c["de"]}" → "{c["a"]}"{nota}')
    else:
        print('\n🔤 Sin correcciones de texto necesarias.')

    if cambios_muletillas:
        print(f'\n🗑️  Muletillas eliminadas ({len(cambios_muletillas)} patrones):')
        for c in cambios_muletillas:
            print(f'   {c["conteo"]:>4}x  patrón: {c["patron"]}')
    else:
        print('\n🗑️  Sin muletillas encontradas.')

    print('─' * 55)
    print(f'Total de cambios: {total}')
    print(f'Backup guardado : {backup_path.name}')


def main():
    print('=' * 55)
    print('  JIFU Knowledge Base — Limpieza Semántica')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 55)

    # Verificar que el KB existe
    if not KB_PATH.exists():
        print(f'\n❌ No se encontró {KB_PATH}')
        print('   Ejecuta primero update_jifu_knowledge.py')
        sys.exit(1)

    # Crear backup antes de modificar
    backup_path = crear_backup()
    print(f'\n💾 Backup creado: {backup_path.name}')

    # Cargar texto del KB
    texto_original = KB_PATH.read_text(encoding='utf-8')
    texto = texto_original

    # Cargar correcciones del archivo editable
    correcciones = cargar_correcciones()

    # Aplicar reemplazos de texto
    print('\n⚙️  Aplicando correcciones de texto...')
    texto, cambios_reemplazos = aplicar_reemplazos(texto, correcciones.get('reemplazos', []))

    # Aplicar limpieza de muletillas
    print('⚙️  Eliminando muletillas...')
    texto, cambios_muletillas = aplicar_muletillas(texto, correcciones.get('muletillas', []))

    # Limpiar espacios extra resultantes
    texto = limpiar_espacios_extra(texto)

    # Verificar si hubo cambios reales
    total_cambios = sum(c['conteo'] for c in cambios_reemplazos + cambios_muletillas)

    if total_cambios == 0:
        print('\n✅ El KB ya está limpio. No se realizaron modificaciones.')
        # Eliminar backup si no hubo cambios (no es necesario)
        backup_path.unlink()
        print('   Backup eliminado (no era necesario).')
        sys.exit(0)

    # Guardar el KB limpio
    KB_PATH.write_text(texto, encoding='utf-8')

    # Mostrar reporte
    imprimir_reporte(cambios_reemplazos, cambios_muletillas, backup_path)

    kb_size = KB_PATH.stat().st_size / 1024
    print(f'\n✅ KB guardado: {KB_PATH.name} ({kb_size:.1f} KB)')
    print('=' * 55)


if __name__ == '__main__':
    main()
