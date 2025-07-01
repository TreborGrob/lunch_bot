#!/bin/bash
# wait-for-mysql.sh

set -e

host="$1"
shift
cmd="$@"

until mysqladmin ping -h "$host" --silent; do
  echo "⏳ Ждём MySQL..."
  sleep 2
done

echo "✅ MySQL готов, запускаем команду: $cmd"
exec $cmd
