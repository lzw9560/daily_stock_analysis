#!/bin/sh
set -eu

APP_USER="dsa"
APP_GROUP="dsa"
APP_UID="1000"
APP_GID="1000"
WRITABLE_DIRS="/app/data /app/logs /app/reports /home/dsa/.longbridge /usr/local/lib/python3.11/site-packages/efinance/data /usr/local/lib/python3.11/site-packages/efinance/config"
DATABASE_FILE="${DATABASE_PATH:-/app/data/stock_analysis.db}"

warn() {
    printf '%s\n' "$*" >&2
}

# 确保 efinance 目录存在（可能被 volume mount 覆盖）
mkdir -p /usr/local/lib/python3.11/site-packages/efinance/data /usr/local/lib/python3.11/site-packages/efinance/config

# 配置 mootdx 最快服务器 IP（避免 K 线获取失败）
# 必须在 dsa 用户下运行，否则 config.json 会变为 root 权限导致
# 后续 K 线请求无法读取配置（No such file or directory）
mkdir -p /home/dsa/.mootdx
if ! gosu dsa python -m mootdx bestip 2>/dev/null; then
    warn "WARN: mootdx bestip failed, generating fallback default config"
    cat > /home/dsa/.mootdx/config.json << 'JSONEOF'
{"SERVER": {"HQ":[["默认行情线路","113.105.73.88",7709]],"EX":[["默认扩展线路","61.152.107.141",7720]],"GP":[["默认财务数据线路","120.76.152.87",7709]]},"BESTIP":{"HQ":["113.105.73.88",7709],"EX":["61.152.107.141",7720],"GP":["120.76.152.87",7709]}}
JSONEOF
fi
chown -R dsa:dsa /home/dsa/.mootdx

can_write_dir_as_app_user() {
    gosu "$APP_USER:$APP_GROUP" sh -c '
        tmp="$1/.dsa-write-check.$$"
        : > "$tmp" && rm -f "$tmp"
    ' sh "$1"
}

can_write_file_as_app_user() {
    gosu "$APP_USER:$APP_GROUP" test -w "$1"
}

has_unwritable_mount_path() {
    dir="$1"

    if ! can_write_dir_as_app_user "$dir"; then
        return 0
    fi

    if [ "$dir" = "/app/data" ]; then
        for file in "$DATABASE_FILE" "$DATABASE_FILE-wal" "$DATABASE_FILE-shm"; do
            if [ -e "$file" ] && ! can_write_file_as_app_user "$file"; then
                return 0
            fi
        done
    fi

    return 1
}

directory_needs_repair() {
    dir="$1"

    if has_unwritable_mount_path "$dir"; then
        return 0
    fi

    mismatched_path="$(
        find "$dir" \
            \( ! -user "$APP_UID" -o ! -group "$APP_GID" \) \
            -print -quit 2>/dev/null || true
    )"
    if [ -n "$mismatched_path" ]; then
        return 0
    fi

    return 1
}

if [ "$(id -u)" = "0" ]; then
    for dir in $WRITABLE_DIRS; do
        if ! mkdir -p "$dir"; then
            warn "WARN: unable to create $dir; application writes may fail for this path."
            continue
        fi

        if ! directory_needs_repair "$dir"; then
            continue
        fi

        if chown -R "$APP_UID:$APP_GID" "$dir"; then
            # 对 efinance 目录使用 a+rwX（而非 u+rwX），确保非 owner 用户也可写
            _chmod_flag="u+rwX"
            case "$dir" in
                */efinance/*) _chmod_flag="a+rwX" ;;
            esac
            if ! chmod -R "$_chmod_flag" "$dir"; then
                warn "WARN: unable to adjust owner permissions for $dir after ownership repair; check read-only, rootless, or NFS mount permissions if writes fail."
            fi
        else
            warn "WARN: unable to set ownership for $dir; skipping owner-only chmod because it would not grant writes to $APP_USER without ownership."
        fi

        if has_unwritable_mount_path "$dir"; then
            warn "WARN: $dir is still not writable by $APP_USER after permission repair; check host mount ownership or read-only, rootless, and NFS mount settings."
        fi
    done

    HOME="/home/dsa"
    export HOME
    exec gosu "$APP_USER:$APP_GROUP" "$@"
fi

exec "$@"
