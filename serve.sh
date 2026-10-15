#!/usr/bin/env bash
# Build and serve the local explorer; no package installation is required.
set -u

usage() {
    cat <<'USAGE'
Usage: bash serve.sh [--python COMMAND] [--port PORT] [--open]

Build the explorer and serve it at http://127.0.0.1:8000/.

  --python COMMAND  Python 3.10+ executable (default: PYTHON or python3)
  --port PORT       Local port (default: 8000; 0 chooses a free port)
  --open            Also open your default browser
  -h, --help        Show this help

Examples:
  bash serve.sh --open
  bash serve.sh --python python --port 0 --open
  bash serve.sh --python "/path with spaces/python3"
USAGE
}

fail() {
    printf 'Error: %s\nRun bash serve.sh --help for usage.\n' "$1" >&2
    exit 2
}

python_command=${PYTHON:-python3}
port=8000
open_browser=0
while (($#)); do
    case "$1" in
        --python|--port)
            option=$1
            (($# >= 2)) || fail "$option needs a value."
            [[ -n $2 && $2 != --* ]] || fail "$option needs a value."
            if [[ $option == --python ]]; then
                python_command=$2
            else
                port=$2
            fi
            shift 2
            ;;
        --python=*) python_command=${1#*=}; shift ;;
        --port=*) port=${1#*=}; shift ;;
        --open) open_browser=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done

[[ $port =~ ^[0-9]+$ ]] || fail 'Use a port number from 0 to 65535.'
# Remove leading zeroes before arithmetic, avoiding octal and overflow.
while [[ ${#port} -gt 1 && $port == 0* ]]; do port=${port#0}; done
[[ ${#port} -le 5 ]] && ((port <= 65535)) || fail 'Use a port number from 0 to 65535.'
[[ -n $python_command ]] || fail '--python needs a Python executable.'
if ! command -v "$python_command" >/dev/null 2>&1; then
    printf 'Cannot find Python executable: %s\nInstall Python 3.10+ or choose it with --python /path/to/python3.\n' "$python_command" >&2
    exit 1
fi
if ! "$python_command" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    printf 'The selected executable must be Python 3.10+: %s\nChoose another executable with --python.\n' "$python_command" >&2
    exit 1
fi

script_directory=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
helper=$script_directory/tools/serve_site.py
trap 'printf "\nLocal preview stopped.\n"; exit 0' INT

if "$python_command" "$helper" build; then
    # Replace Bash so Ctrl+C reaches the server directly.
    exec "$python_command" "$helper" serve "$port" "$open_browser"
else
    status=$?
    if ((status == 130)); then
        printf '\nLocal preview stopped.\n'
        exit 0
    fi
    exit "$status"
fi
