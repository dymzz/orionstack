#!/bin/sh
set -eu

copy_defaults_if_empty() {
    source_dir="$1"
    target_dir="$2"

    mkdir -p "$target_dir"
    if [ -d "$source_dir" ] && ! find "$target_dir" -type f -name '*.jsonl' | grep -q .; then
        cp -a "$source_dir"/. "$target_dir"/
    fi
}

copy_defaults_if_empty /app/default-storage/action_links /app/backend/app/storage/action_links
copy_defaults_if_empty /app/default-storage/dynamic_queries /app/backend/app/storage/dynamic_queries

exec "$@"
