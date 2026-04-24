#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_to_drive.py
────────────────
Sube jifu_knowledge_base.md a Google Drive.
- Si ya existe un archivo con ese nombre en la carpeta destino, lo reemplaza.
- Verifica el éxito comparando el tamaño local con el registrado en Drive.
- Reintenta automáticamente hasta 3 veces ante errores de red.

Uso:
    python3 sync_to_drive.py
"""

import sys
import time
import pickle
import os
from datetime import datetime
from pathlib import Path

# ── Rutas y configuración ────────────────────────────────────────────────────
BASE_DIR       = Path('/root/jifu-knowledge')
KB_PATH        = BASE_DIR / 'jifu_knowledge_base.md'
TOKEN_PATH     = Path('/root/drive_token.pickle')
CREDENCIALES   = BASE_DIR / 'credentials.json'

# ID de la carpeta "Base de Conocimiento" en Google Drive
CARPETA_DRIVE_ID = '1XIY-pm-dCZkJNGkZy_U4-1aVNOLYNZnn'
NOMBRE_ARCHIVO   = 'jifu_knowledge_base.md'
MAX_REINTENTOS   = 3
PAUSA_REINTENTO  = 5  # segundos entre reintentos


def instalar_dependencias():
    """Instala google-api-python-client si no está disponible."""
    try:
        from googleapiclient.discovery import build  # noqa
    except ImportError:
        print('📦 Instalando google-api-python-client...')
        os.system(f'{sys.executable} -m pip install -q google-api-python-client google-auth-httplib2 google-auth-oauthlib')


def obtener_servicio_drive():
    """
    Carga credenciales desde drive_token.pickle y devuelve el servicio Drive.
    Refresca el token automáticamente si está expirado.
    """
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_PATH.exists():
        print(f'❌ No se encontró el token de Drive en {TOKEN_PATH}')
        print('   Ejecuta primero: python3 /root/drive_cleanup.py')
        sys.exit(1)

    with open(TOKEN_PATH, 'rb') as f:
        creds = pickle.load(f)

    # Refrescar si está expirado pero tiene refresh_token
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print('🔄 Token expirado — refrescando automáticamente...')
            creds.refresh(Request())
            with open(TOKEN_PATH, 'wb') as f:
                pickle.dump(creds, f)
            print('   Token actualizado.')
        else:
            print('❌ El token de Drive no es válido y no puede refrescarse.')
            print('   Ejecuta: python3 /root/drive_cleanup.py  para re-autenticar.')
            sys.exit(1)

    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def buscar_archivo_en_drive(servicio, nombre: str, carpeta_id: str) -> str | None:
    """
    Busca un archivo por nombre en la carpeta indicada.
    Devuelve el ID del primer resultado o None si no existe.
    """
    query = (
        f"name='{nombre}' "
        f"and '{carpeta_id}' in parents "
        f"and trashed=false"
    )
    resultado = servicio.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, size)',
    ).execute()

    archivos = resultado.get('files', [])
    return archivos[0]['id'] if archivos else None


def subir_con_reintentos(servicio, intento_fn, descripcion: str):
    """Ejecuta intento_fn() con reintentos automáticos ante errores de red."""
    from googleapiclient.errors import HttpError

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            return intento_fn()
        except HttpError as e:
            if intento == MAX_REINTENTOS:
                raise
            print(f'   ⚠️  Intento {intento}/{MAX_REINTENTOS} fallido ({e.status_code}). '
                  f'Reintentando en {PAUSA_REINTENTO}s...')
            time.sleep(PAUSA_REINTENTO)
        except Exception as e:
            if intento == MAX_REINTENTOS:
                raise
            print(f'   ⚠️  Intento {intento}/{MAX_REINTENTOS} fallido ({e}). '
                  f'Reintentando en {PAUSA_REINTENTO}s...')
            time.sleep(PAUSA_REINTENTO)


def main():
    print('=' * 55)
    print('  JIFU Knowledge Base — Sincronización Drive')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 55)

    # Verificar que el KB existe
    if not KB_PATH.exists():
        print(f'\n❌ No se encontró {KB_PATH}')
        print('   Ejecuta primero update_jifu_knowledge.py')
        sys.exit(1)

    instalar_dependencias()

    from googleapiclient.http import MediaFileUpload

    tamano_local = KB_PATH.stat().st_size
    print(f'\n📄 Archivo local : {KB_PATH.name}')
    print(f'   Tamaño        : {tamano_local / 1024:.1f} KB ({tamano_local:,} bytes)')

    # Conectar con Drive
    print('\n🔌 Conectando con Google Drive...')
    servicio = obtener_servicio_drive()
    print('   Conexión exitosa.')

    # Buscar si ya existe el archivo en la carpeta destino
    print(f'\n🔍 Buscando "{NOMBRE_ARCHIVO}" en carpeta de Drive...')
    id_existente = buscar_archivo_en_drive(servicio, NOMBRE_ARCHIVO, CARPETA_DRIVE_ID)

    media = MediaFileUpload(
        str(KB_PATH),
        mimetype='text/markdown',
        resumable=True,
    )

    if id_existente:
        print(f'   Archivo existente encontrado (ID: {id_existente})')
        print('   Actualizando (reemplazando contenido)...')

        def actualizar():
            return servicio.files().update(
                fileId=id_existente,
                media_body=media,
                fields='id, name, size, webViewLink',
            ).execute()

        archivo_subido = subir_con_reintentos(servicio, actualizar, 'actualización')
    else:
        print('   No existe — creando archivo nuevo...')
        metadatos = {
            'name':    NOMBRE_ARCHIVO,
            'parents': [CARPETA_DRIVE_ID],
        }

        def crear():
            return servicio.files().create(
                body=metadatos,
                media_body=media,
                fields='id, name, size, webViewLink',
            ).execute()

        archivo_subido = subir_con_reintentos(servicio, crear, 'creación')

    # Verificar integridad comparando tamaños
    tamano_drive = int(archivo_subido.get('size', 0))
    link = archivo_subido.get('webViewLink', 'sin enlace')

    print('\n✅ Subida completada.')
    print(f'   Tamaño local  : {tamano_local:,} bytes')
    print(f'   Tamaño Drive  : {tamano_drive:,} bytes')

    if abs(tamano_local - tamano_drive) <= 10:
        print('   Verificación  : ✅ Tamaños coinciden')
    else:
        print(f'   Verificación  : ⚠️  Diferencia de {abs(tamano_local - tamano_drive)} bytes (puede ser normal por encoding)')

    print(f'\n🔗 Enlace directo:')
    print(f'   {link}')
    print(f'\n📅 Sincronizado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 55)


if __name__ == '__main__':
    main()
