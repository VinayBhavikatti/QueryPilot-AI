#!/bin/bash
set -euo pipefail

escape_sql_string() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\'/\'\'}
  printf '%s' "$value"
}

db_user=$(escape_sql_string "$APP_DB_USER")
db_password=$(escape_sql_string "$APP_DB_PASSWORD")
db_name=${MYSQL_DATABASE//\`/}

mysql --protocol=socket -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
CREATE USER IF NOT EXISTS '$db_user'@'%' IDENTIFIED BY '$db_password';
ALTER USER '$db_user'@'%' IDENTIFIED BY '$db_password';
GRANT SELECT ON \`$db_name\`.* TO '$db_user'@'%';
SQL
