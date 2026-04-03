#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# FORGE — Local Development Service Manager
# ─────────────────────────────────────────────────────────────────────
# Usage:  ./forge.sh <command> [service]
#
# Commands:
#   start   [service|all]    Start service(s)
#   stop    [service|all]    Stop service(s)
#   restart [service|all]    Restart service(s)
#   status                   Show status of all services
#   logs    <service>        Tail logs for a service
#   db:migrate               Run Alembic migrations
#   db:reset                 Reset local database
#   test    [backend|frontend|all]  Run tests
#   build                    Production build frontend
#
# Services:  backend | frontend | postgres | redis
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PID_FILE="$ROOT_DIR/.pids/backend.pid"
FRONTEND_PID_FILE="$ROOT_DIR/.pids/frontend.pid"

BACKEND_LOG="$ROOT_DIR/.logs/backend.log"
FRONTEND_LOG="$ROOT_DIR/.logs/frontend.log"

BACKEND_PORT=8000
FRONTEND_PORT=5173
POSTGRES_PORT=5432
REDIS_PORT=6379

# ── Colors ───────────────────────────────────────────────────────────
R='\033[0;31m'   # red
G='\033[0;32m'   # green
B='\033[0;34m'   # blue
C='\033[0;36m'   # cyan
Y='\033[1;33m'   # yellow
M='\033[0;35m'   # magenta
W='\033[1;37m'   # white
D='\033[0;90m'   # dim
N='\033[0m'      # reset

# ── Helpers ──────────────────────────────────────────────────────────
log()   { echo -e "${C}⚡${N} ${W}$1${N}"; }
ok()    { echo -e "${G}✓${N}  $1"; }
err()   { echo -e "${R}✗${N}  $1"; }
warn()  { echo -e "${Y}!${N}  $1"; }
dim()   { echo -e "${D}   $1${N}"; }

ensure_dirs() {
    mkdir -p "$ROOT_DIR/.pids" "$ROOT_DIR/.logs"
}

header() {
    echo ""
    echo -e "${C}╔══════════════════════════════════════════════════╗${N}"
    echo -e "${C}║${N}  ${W}⚡ FORGE${N} — ${D}Local Development Manager${N}            ${C}║${N}"
    echo -e "${C}╚══════════════════════════════════════════════════╝${N}"
    echo ""
}

# ── Service Checks ───────────────────────────────────────────────────
# Use `ss` for detection — works without root for system services
# (lsof can't see processes owned by postgres/redis users)
is_port_in_use() {
    ss -tlnH "sport = :$1" 2>/dev/null | grep -q "LISTEN" 2>/dev/null
}

# Returns ALL PIDs listening on a port (combines lsof + ss + fuser)
get_all_pids_on_port() {
    {
        lsof -ti :"$1" -sTCP:LISTEN 2>/dev/null
        fuser "$1/tcp" 2>/dev/null | tr ' ' '\n'
    } | grep -v '^$' | sort -un
}

# Returns a single PID for display purposes
get_pid_on_port() {
    get_all_pids_on_port "$1" | head -1
}

is_service_running() {
    local service="$1"
    case "$service" in
        backend)    is_port_in_use $BACKEND_PORT ;;
        frontend)   is_port_in_use $FRONTEND_PORT ;;
        postgres)   is_port_in_use $POSTGRES_PORT ;;
        redis)      is_port_in_use $REDIS_PORT ;;
        *)          return 1 ;;
    esac
}

# ── Process Tree Kill ────────────────────────────────────────────────
# Kills a process and ALL its children (entire process group).
# Strategy:
#   1. Find all PIDs on the port
#   2. For each PID, find its process group (PGID)
#   3. Kill the entire process group with SIGTERM
#   4. Wait, then SIGKILL any survivors
#   5. Also kill any orphaned children by walking the PID file
kill_process_tree() {
    local port="$1"
    local pid_file="${2:-}"
    local killed_count=0
    local pids_to_kill=""

    # Collect all PIDs on the port
    local port_pids
    port_pids=$(get_all_pids_on_port "$port")

    # Also include PID from pid file (parent may not be listening)
    if [ -n "$pid_file" ] && [ -f "$pid_file" ]; then
        local file_pid
        file_pid=$(cat "$pid_file" 2>/dev/null || true)
        if [ -n "$file_pid" ] && kill -0 "$file_pid" 2>/dev/null; then
            port_pids=$(printf "%s\n%s" "$port_pids" "$file_pid" | sort -u)
        fi
    fi

    if [ -z "$port_pids" ]; then
        return 0
    fi

    # For each PID: find its children and process group
    local all_pids=""
    for pid in $port_pids; do
        # Add the PID itself
        all_pids=$(printf "%s\n%s" "$all_pids" "$pid")

        # Add all child PIDs (recursive via pgrep)
        local children
        children=$(pgrep -P "$pid" 2>/dev/null || true)
        if [ -n "$children" ]; then
            all_pids=$(printf "%s\n%s" "$all_pids" "$children")
        fi

        # Walk up to find grandchildren too
        for child in $children; do
            local grandchildren
            grandchildren=$(pgrep -P "$child" 2>/dev/null || true)
            if [ -n "$grandchildren" ]; then
                all_pids=$(printf "%s\n%s" "$all_pids" "$grandchildren")
            fi
        done
    done

    # Deduplicate
    all_pids=$(echo "$all_pids" | grep -v '^$' | sort -u)

    if [ -z "$all_pids" ]; then
        return 0
    fi

    # Phase 1: SIGTERM all PIDs (graceful)
    for pid in $all_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            killed_count=$((killed_count + 1))
        fi
    done

    # Wait up to 3 seconds for graceful shutdown
    local wait=0
    while [ $wait -lt 6 ]; do
        local any_alive=false
        for pid in $all_pids; do
            if kill -0 "$pid" 2>/dev/null; then
                any_alive=true
                break
            fi
        done
        if [ "$any_alive" = false ]; then
            break
        fi
        sleep 0.5
        wait=$((wait + 1))
    done

    # Phase 2: SIGKILL any survivors
    for pid in $all_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
            dim "Force-killed PID $pid"
        fi
    done

    # Clean up PID file
    if [ -n "$pid_file" ]; then
        rm -f "$pid_file"
    fi

    dim "Killed $killed_count process(es) on :$port"
}

# ── Start ────────────────────────────────────────────────────────────
start_postgres() {
    if is_service_running postgres; then
        ok "PostgreSQL already running on :${POSTGRES_PORT}"
        return 0
    fi
    log "Starting PostgreSQL..."
    if systemctl is-enabled postgresql >/dev/null 2>&1; then
        sudo systemctl start postgresql 2>/dev/null
    elif command -v pg_ctlcluster >/dev/null 2>&1; then
        sudo pg_ctlcluster 16 main start 2>/dev/null
    elif command -v pg_ctl >/dev/null 2>&1; then
        pg_ctl -D "$BACKEND_DIR/.pgdata" start 2>/dev/null
    else
        err "PostgreSQL not found — install it or start manually"
        return 1
    fi
    sleep 1
    if is_service_running postgres; then
        ok "PostgreSQL started on :${POSTGRES_PORT}"
    else
        err "PostgreSQL failed to start — check: sudo journalctl -u postgresql"
        return 1
    fi
}

start_redis() {
    if is_service_running redis; then
        ok "Redis already running on :${REDIS_PORT}"
        return 0
    fi
    log "Starting Redis..."
    # Try systemctl first (most Linux systems)
    if systemctl is-enabled redis-server >/dev/null 2>&1; then
        sudo systemctl start redis-server 2>/dev/null
    elif systemctl is-enabled redis >/dev/null 2>&1; then
        sudo systemctl start redis 2>/dev/null
    elif command -v redis-server >/dev/null 2>&1; then
        redis-server --daemonize yes --port "$REDIS_PORT" --loglevel warning 2>/dev/null
    else
        warn "Redis not installed — some features will use in-memory fallback"
        return 0
    fi
    sleep 0.5
    if is_service_running redis; then
        ok "Redis started on :${REDIS_PORT}"
    else
        err "Redis failed to start — check: sudo journalctl -u redis-server"
        return 1
    fi
}

start_backend() {
    if is_service_running backend; then
        ok "Backend already running on :${BACKEND_PORT}"
        return 0
    fi
    log "Starting Backend (FastAPI)..."
    ensure_dirs
    cd "$BACKEND_DIR"
    nohup uvicorn app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$BACKEND_PID_FILE"
    cd "$ROOT_DIR"

    # Wait for startup
    local tries=0
    while [ $tries -lt 20 ]; do
        if is_service_running backend; then
            ok "Backend started on :${BACKEND_PORT}  (PID: $pid)"
            return 0
        fi
        sleep 0.5
        tries=$((tries + 1))
    done
    err "Backend failed to start — check: ${BACKEND_LOG}"
    return 1
}

start_frontend() {
    if is_service_running frontend; then
        ok "Frontend already running on :${FRONTEND_PORT}"
        return 0
    fi
    log "Starting Frontend (Vite)..."
    ensure_dirs
    cd "$FRONTEND_DIR"
    nohup npm run dev -- --host 0.0.0.0 > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRONTEND_PID_FILE"
    cd "$ROOT_DIR"

    local tries=0
    while [ $tries -lt 20 ]; do
        if is_service_running frontend; then
            ok "Frontend started on :${FRONTEND_PORT}  (PID: $pid)"
            return 0
        fi
        sleep 0.5
        tries=$((tries + 1))
    done
    err "Frontend failed to start — check: ${FRONTEND_LOG}"
    return 1
}

start_service() {
    local service="${1:-all}"
    case "$service" in
        backend)    start_backend ;;
        frontend)   start_frontend ;;
        postgres)   start_postgres ;;
        redis)      start_redis ;;
        all)
            start_postgres
            start_redis
            start_backend
            start_frontend
            echo ""
            show_status
            ;;
        *) err "Unknown service: $service"; usage ;;
    esac
}

# ── Stop ─────────────────────────────────────────────────────────────
stop_backend() {
    if ! is_service_running backend; then
        dim "Backend not running"
        return 0
    fi
    log "Stopping Backend (uvicorn + all workers)..."
    kill_process_tree "$BACKEND_PORT" "$BACKEND_PID_FILE"
    if is_service_running backend; then
        err "Backend still has processes on :${BACKEND_PORT} — force killing"
        # Nuclear option: kill everything on the port
        lsof -ti :"$BACKEND_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fi
    ok "Backend stopped"
}

stop_frontend() {
    if ! is_service_running frontend; then
        dim "Frontend not running"
        return 0
    fi
    log "Stopping Frontend (vite + all node children)..."
    kill_process_tree "$FRONTEND_PORT" "$FRONTEND_PID_FILE"
    if is_service_running frontend; then
        err "Frontend still has processes on :${FRONTEND_PORT} — force killing"
        lsof -ti :"$FRONTEND_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fi
    ok "Frontend stopped"
}

stop_redis() {
    if ! is_service_running redis; then
        dim "Redis not running"
        return 0
    fi
    log "Stopping Redis..."
    redis-cli -p "$REDIS_PORT" shutdown 2>/dev/null \
        || kill_process_tree "$REDIS_PORT" "" \
        || true
    sleep 0.5
    # Verify it's actually dead
    if is_service_running redis; then
        lsof -ti :"$REDIS_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fi
    ok "Redis stopped"
}

stop_postgres() {
    if ! is_service_running postgres; then
        dim "PostgreSQL not running"
        return 0
    fi
    log "Stopping PostgreSQL..."
    if systemctl is-enabled postgresql >/dev/null 2>&1; then
        sudo systemctl stop postgresql 2>/dev/null
    elif command -v pg_ctlcluster >/dev/null 2>&1; then
        sudo pg_ctlcluster 16 main stop 2>/dev/null
    else
        warn "Stop PostgreSQL manually via pg_ctl"
        return 0
    fi
    sleep 1
    if is_service_running postgres; then
        warn "PostgreSQL still running — may need: sudo systemctl stop postgresql"
    else
        ok "PostgreSQL stopped"
    fi
}

stop_service() {
    local service="${1:-all}"
    case "$service" in
        backend)    stop_backend ;;
        frontend)   stop_frontend ;;
        postgres)   stop_postgres ;;
        redis)      stop_redis ;;
        all)
            stop_frontend
            stop_backend
            stop_redis
            echo ""
            ok "All FORGE services stopped"
            ;;
        *) err "Unknown service: $service"; usage ;;
    esac
}

# ── Restart ──────────────────────────────────────────────────────────
restart_service() {
    local service="${1:-all}"
    log "Restarting ${service}..."
    stop_service "$service"
    sleep 1
    start_service "$service"
}

# ── Status ───────────────────────────────────────────────────────────
show_status() {
    echo -e "${W}  Service        Port    Status${N}"
    echo -e "${D}  ─────────────  ──────  ──────────────${N}"

    local services=("postgres:${POSTGRES_PORT}" "redis:${REDIS_PORT}" "backend:${BACKEND_PORT}" "frontend:${FRONTEND_PORT}")
    local icons=("🐘" "🔴" "⚡" "⚛️ ")
    local i=0

    for entry in "${services[@]}"; do
        local svc="${entry%%:*}"
        local port="${entry##*:}"
        local icon="${icons[$i]}"
        local status_text

        if is_service_running "$svc"; then
            local pid
            pid=$(get_pid_on_port "$port" 2>/dev/null || true)
            if [ -n "$pid" ]; then
                status_text="${G}● Running${N}  ${D}(PID: ${pid})${N}"
            else
                status_text="${G}● Running${N}"
            fi
        else
            status_text="${R}○ Stopped${N}"
        fi

        printf "  %s %-12s  :%-5s  %b\n" "$icon" "$svc" "$port" "$status_text"
        i=$((i + 1))
    done
    echo ""
}

# ── Logs ─────────────────────────────────────────────────────────────
show_logs() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        err "Specify a service: logs <backend|frontend>"
        exit 1
    fi

    case "$service" in
        backend)
            if [ -f "$BACKEND_LOG" ]; then
                log "Tailing backend logs (Ctrl+C to exit)..."
                tail -f "$BACKEND_LOG"
            else
                err "No backend log file — start the backend first"
            fi
            ;;
        frontend)
            if [ -f "$FRONTEND_LOG" ]; then
                log "Tailing frontend logs (Ctrl+C to exit)..."
                tail -f "$FRONTEND_LOG"
            else
                err "No frontend log file — start the frontend first"
            fi
            ;;
        postgres)
            log "PostgreSQL logs:"
            sudo journalctl -u postgresql --no-pager -n 50 2>/dev/null \
                || warn "Use: sudo journalctl -u postgresql"
            ;;
        redis)
            log "Redis logs:"
            redis-cli -p "$REDIS_PORT" INFO server 2>/dev/null | head -20 \
                || warn "Redis not running"
            ;;
        *)
            err "Unknown service: $service"
            ;;
    esac
}

# ── Database ─────────────────────────────────────────────────────────
db_migrate() {
    log "Running Alembic migrations..."
    cd "$BACKEND_DIR"
    alembic upgrade head
    ok "Migrations complete"
    cd "$ROOT_DIR"
}

db_reset() {
    warn "This will DROP and recreate the forge_dev database!"
    read -rp "Are you sure? (y/N) " confirm
    if [[ "$confirm" != [yY] ]]; then
        dim "Cancelled"
        return 0
    fi
    log "Resetting database..."
    psql -U forge_dev -d postgres -c "DROP DATABASE IF EXISTS forge_dev;" 2>/dev/null || true
    psql -U forge_dev -d postgres -c "CREATE DATABASE forge_dev;" 2>/dev/null || true
    cd "$BACKEND_DIR"
    alembic upgrade head
    ok "Database reset and migrated"
    cd "$ROOT_DIR"
}

# ── Tests ────────────────────────────────────────────────────────────
run_tests() {
    local target="${1:-all}"
    case "$target" in
        backend)
            log "Running backend tests..."
            cd "$BACKEND_DIR"
            python -m pytest tests/ -v --tb=short
            cd "$ROOT_DIR"
            ;;
        frontend)
            log "Running frontend typecheck + lint..."
            cd "$FRONTEND_DIR"
            npx tsc --noEmit
            npm run lint 2>/dev/null || true
            cd "$ROOT_DIR"
            ;;
        all)
            run_tests backend
            echo ""
            run_tests frontend
            ;;
        *)
            err "Unknown target: $target (use: backend|frontend|all)"
            ;;
    esac
}

# ── Build ────────────────────────────────────────────────────────────
build_frontend() {
    log "Building frontend for production..."
    cd "$FRONTEND_DIR"
    npm run build
    ok "Frontend built → dist/"
    cd "$ROOT_DIR"
}

# ── Usage ────────────────────────────────────────────────────────────
usage() {
    echo ""
    echo -e "${W}Usage:${N}  ./forge.sh ${C}<command>${N} [${M}service${N}]"
    echo ""
    echo -e "${W}Commands:${N}"
    echo -e "  ${C}start${N}   [${M}service|all${N}]       Start service(s)          ${D}default: all${N}"
    echo -e "  ${C}stop${N}    [${M}service|all${N}]       Stop service(s)           ${D}default: all${N}"
    echo -e "  ${C}restart${N} [${M}service|all${N}]       Restart service(s)        ${D}default: all${N}"
    echo -e "  ${C}status${N}                      Show status of all services"
    echo -e "  ${C}logs${N}    ${M}<service>${N}            Tail logs for a service"
    echo -e "  ${C}test${N}    [${M}backend|frontend|all${N}]  Run tests             ${D}default: all${N}"
    echo -e "  ${C}build${N}                       Production build frontend"
    echo -e "  ${C}db:migrate${N}                  Run Alembic migrations"
    echo -e "  ${C}db:reset${N}                    Reset local database"
    echo ""
    echo -e "${W}Services:${N}  ${M}backend${N} | ${M}frontend${N} | ${M}postgres${N} | ${M}redis${N}"
    echo ""
    echo -e "${W}Examples:${N}"
    echo -e "  ${D}./forge.sh start${N}              ${D}# Start everything${N}"
    echo -e "  ${D}./forge.sh restart backend${N}     ${D}# Restart only backend${N}"
    echo -e "  ${D}./forge.sh logs backend${N}        ${D}# Tail backend logs${N}"
    echo -e "  ${D}./forge.sh status${N}              ${D}# Show all service statuses${N}"
    echo -e "  ${D}./forge.sh test${N}                ${D}# Run all tests${N}"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────
main() {
    local cmd="${1:-}"
    local arg="${2:-}"

    if [ -z "$cmd" ]; then
        header
        usage
        exit 0
    fi

    header

    case "$cmd" in
        start)      start_service "$arg" ;;
        stop)       stop_service "$arg" ;;
        restart)    restart_service "$arg" ;;
        status)     show_status ;;
        logs)       show_logs "$arg" ;;
        test)       run_tests "$arg" ;;
        build)      build_frontend ;;
        db:migrate) db_migrate ;;
        db:reset)   db_reset ;;
        -h|--help|help) usage ;;
        *)
            err "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
