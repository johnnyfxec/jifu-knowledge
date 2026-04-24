#!/bin/bash
# run_jifu_pipeline.sh
# ─────────────────────────────────────────────────────────────
# Orquestador del sistema JIFU Knowledge Base.
# Ejecuta los tres componentes en orden y reporta el resultado.
#
# Uso:
#   bash run_jifu_pipeline.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

DIR_BASE="/root/jifu-knowledge"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_PIPELINE="/tmp/jifu_pipeline_${TIMESTAMP}.log"
INICIO=$(date +%s)

# ── Colores ──────────────────────────────────────────────────
VERDE="\033[0;32m"
ROJO="\033[0;31m"
AMARILLO="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# ── Funciones de log ─────────────────────────────────────────
stamp()     { date '+%Y-%m-%d %H:%M:%S'; }
log()       { echo -e "$(stamp)  $1" | tee -a "$LOG_PIPELINE"; }
log_ok()    { log "${VERDE}${BOLD}✅ $1${RESET}"; }
log_error() { log "${ROJO}${BOLD}❌ $1${RESET}"; }
log_info()  { log "${CYAN}ℹ️  $1${RESET}"; }
log_warn()  { log "${AMARILLO}⚠️  $1${RESET}"; }
log_sep()   { log "────────────────────────────────────────────────────"; }

# ── Encabezado ───────────────────────────────────────────────
echo "" | tee -a "$LOG_PIPELINE"
log "${BOLD}════════════════════════════════════════════════════${RESET}"
log "${BOLD}  JIFU Knowledge Pipeline — Inicio${RESET}"
log "${BOLD}════════════════════════════════════════════════════${RESET}"
log_info "Log de esta ejecución: $LOG_PIPELINE"

cd "$DIR_BASE"

# ── PASO 1/3: Actualizar Knowledge Base ──────────────────────
log_sep
log_info "PASO 1/3 — Detectando transcripciones nuevas..."

SALIDA_UPDATE=$(python3 update_jifu_knowledge.py 2>&1) || {
    echo "$SALIDA_UPDATE" | tee -a "$LOG_PIPELINE"
    log_error "Fallo en update_jifu_knowledge.py — pipeline detenido."
    exit 1
}
echo "$SALIDA_UPDATE" | tee -a "$LOG_PIPELINE"

# Si no hay archivos nuevos, salir limpiamente sin ejecutar los pasos siguientes
if echo "$SALIDA_UPDATE" | grep -q "El knowledge base está al día"; then
    log_warn "Sin transcripciones nuevas. No hay cambios que limpiar ni sincronizar."
    FIN=$(date +%s)
    echo "" | tee -a "$LOG_PIPELINE"
    log "${BOLD}════════════════════════════════════════════════════${RESET}"
    log "${BOLD}  Pipeline finalizado (sin cambios)${RESET}"
    log "  Tiempo total: $((FIN - INICIO))s"
    log "${BOLD}════════════════════════════════════════════════════${RESET}"
    exit 0
fi

# Extraer cantidad de transcripciones procesadas
PROCESADOS=$(echo "$SALIDA_UPDATE" | grep -oP 'Completado: \K\d+' || echo "0")
log_ok "Knowledge base actualizado. Transcripciones procesadas: $PROCESADOS"

# ── PASO 2/3: Limpieza semántica ─────────────────────────────
log_sep
log_info "PASO 2/3 — Aplicando limpieza semántica..."

SALIDA_CLEAN=$(python3 clean_jifu_knowledge.py 2>&1) || {
    echo "$SALIDA_CLEAN" | tee -a "$LOG_PIPELINE"
    log_error "Fallo en clean_jifu_knowledge.py — pipeline detenido."
    exit 1
}
echo "$SALIDA_CLEAN" | tee -a "$LOG_PIPELINE"

CORRECCIONES=$(echo "$SALIDA_CLEAN" | grep -oP 'Total de cambios: \K\d+' || echo "0")
log_ok "Limpieza completada. Cambios realizados: $CORRECCIONES"

# ── PASO 3/3: Sincronización con Drive ───────────────────────
log_sep
log_info "PASO 3/3 — Sincronizando con Google Drive..."

SALIDA_SYNC=$(python3 sync_to_drive.py 2>&1) || {
    echo "$SALIDA_SYNC" | tee -a "$LOG_PIPELINE"
    log_error "Fallo en sync_to_drive.py — pipeline detenido."
    exit 1
}
echo "$SALIDA_SYNC" | tee -a "$LOG_PIPELINE"

LINK_DRIVE=$(echo "$SALIDA_SYNC" | grep "https://drive.google.com" | xargs || echo "sin enlace")
log_ok "Sincronización completada."

# ── Resumen final ─────────────────────────────────────────────
FIN=$(date +%s)
DURACION=$((FIN - INICIO))

echo "" | tee -a "$LOG_PIPELINE"
log "${BOLD}════════════════════════════════════════════════════${RESET}"
log "${BOLD}  ✅ PIPELINE COMPLETADO EXITOSAMENTE${RESET}"
log "${BOLD}════════════════════════════════════════════════════${RESET}"
log "  📊 Transcripciones procesadas : $PROCESADOS"
log "  ✏️  Correcciones semánticas    : $CORRECCIONES"
log "  ☁️  Sincronizado con Drive     : ✅"
log "  🔗 Enlace                     : $LINK_DRIVE"
log "  ⏱️  Tiempo total               : ${DURACION}s"
log "  📋 Log completo               : $LOG_PIPELINE"
log "${BOLD}════════════════════════════════════════════════════${RESET}"
