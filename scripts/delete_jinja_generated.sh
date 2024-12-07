SCRIPT_DIR=$(realpath "$(dirname "$0")")
HELPER_DIR="$SCRIPT_DIR/helper"
TOML_FILE="$SCRIPT_DIR/../config.toml"

python3 "$HELPER_DIR"/delete_jinja_generated.py "$TOML_FILE"
