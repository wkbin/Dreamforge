#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${ZAOMENG_REPO_SLUG:-wkbin/zaomeng}"
REPO_REF="${ZAOMENG_REF:-main}"
INSTALL_ROOT="${ZAOMENG_INSTALL_DIR:-$HOME/.local/share/zaomeng}"
BIN_DIR="${ZAOMENG_BIN_DIR:-$HOME/.local/bin}"
PYTHON_BIN="${ZAOMENG_PYTHON:-}"
RUNTIME_REQUIREMENTS_FILE="${ZAOMENG_REQUIREMENTS_FILE:-requirements.runtime.txt}"
TMP_DIR=""

cleanup() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "${TMP_DIR:-}" ]; then
    rm -rf "$TMP_DIR"
  fi
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

choose_python() {
  if [ -n "$PYTHON_BIN" ]; then
    echo "$PYTHON_BIN"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo python
    return
  fi
  echo "Python 3 is required. Please install python3 first." >&2
  exit 1
}

choose_fetch() {
  if command -v curl >/dev/null 2>&1; then
    echo curl
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    echo wget
    return
  fi
  echo "curl or wget is required." >&2
  exit 1
}

detect_rc_file() {
  if [ -n "${ZDOTDIR:-}" ] && [ -f "${ZDOTDIR}/.zshrc" ]; then
    echo "${ZDOTDIR}/.zshrc"
    return
  fi
  if [ -n "${SHELL:-}" ] && [[ "${SHELL}" == *zsh ]]; then
    echo "$HOME/.zshrc"
    return
  fi
  if [ -f "$HOME/.bashrc" ]; then
    echo "$HOME/.bashrc"
    return
  fi
  echo "$HOME/.profile"
}

append_path_line() {
  local rc_file="$1"
  local path_line='export PATH="$HOME/.local/bin:$PATH"'
  mkdir -p "$(dirname "$rc_file")"
  touch "$rc_file"
  if ! grep -Fq "$path_line" "$rc_file"; then
    printf '\n%s\n' "$path_line" >>"$rc_file"
  fi
}

fetch_archive() {
  local url="$1"
  local output="$2"
  local fetcher="$3"
  if [ "$fetcher" = "curl" ]; then
    curl --fail --silent --show-error --location \
      --retry 3 --retry-delay 2 --retry-all-errors \
      "$url" -o "$output"
  else
    wget --tries=3 --waitretry=2 -O "$output" "$url"
  fi
}

main() {
  need_cmd tar
  need_cmd mktemp
  need_cmd chmod

  local python_cmd
  python_cmd="$(choose_python)"
  local fetcher
  fetcher="$(choose_fetch)"

  TMP_DIR="$(mktemp -d)"
  trap cleanup EXIT

  local archive_url="https://github.com/${REPO_SLUG}/archive/${REPO_REF}.tar.gz"
  local archive_path="${TMP_DIR}/zaomeng.tar.gz"
  local extract_root="${TMP_DIR}/extract"
  local venv_dir="${INSTALL_ROOT}/.venv"
  local launcher_path="${BIN_DIR}/zaomeng"
  local requirements_path="${INSTALL_ROOT}/${RUNTIME_REQUIREMENTS_FILE}"
  local extracted_dir
  local rc_file
  rc_file="$(detect_rc_file)"

  mkdir -p "$extract_root" "$BIN_DIR" "$(dirname "$INSTALL_ROOT")"

  echo "Downloading ${archive_url}"
  if ! fetch_archive "$archive_url" "$archive_path" "$fetcher"; then
    echo "Failed to download ${archive_url}. Please check your network connection and try again." >&2
    exit 1
  fi

  rm -rf "$INSTALL_ROOT"
  tar -xzf "$archive_path" -C "$extract_root"
  extracted_dir="$(find "$extract_root" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [ -z "$extracted_dir" ]; then
    echo "Failed to locate extracted repository directory." >&2
    exit 1
  fi
  mv "$extracted_dir" "$INSTALL_ROOT"

  if [ ! -f "$requirements_path" ]; then
    echo "Missing runtime requirements file: ${requirements_path}" >&2
    exit 1
  fi

  echo "Creating virtual environment"
  "$python_cmd" -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install --upgrade pip setuptools wheel
  "$venv_dir/bin/python" -m pip install -r "$requirements_path"

  cat >"$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT}"
PYTHON_BIN="\${INSTALL_ROOT}/.venv/bin/python"

if [ ! -x "\${PYTHON_BIN}" ]; then
  echo "zaomeng runtime is missing: \${PYTHON_BIN}" >&2
  exit 1
fi

if [ \$# -eq 0 ]; then
  exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/run_webui.py"
fi

case "\$1" in
  web)
    shift
    exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/run_webui.py" "\$@"
    ;;
  bump-web-assets)
    shift
    if [ \$# -eq 0 ]; then
      exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/web_asset_version.py" --bump
    fi
    exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/web_asset_version.py" --version "\$1"
    ;;
  install-skill)
    shift
    exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/install_skill.py" "\$@"
    ;;
  version)
    exec "\${PYTHON_BIN}" - <<PY
from pathlib import Path
print(Path("${INSTALL_ROOT}/src/web/static/version.txt").read_text(encoding="utf-8").strip())
PY
    ;;
  help|-h|--help)
    cat <<'HELP'
zaomeng commands:
  zaomeng                Start the Web UI on 127.0.0.1:8000
  zaomeng web [args]     Forward args to scripts/run_webui.py
  zaomeng bump-web-assets [version]
                         Bump or explicitly sync the static asset version
  zaomeng install-skill [args]
                         Forward args to scripts/install_skill.py
  zaomeng version        Print the current web static asset version
HELP
    ;;
  *)
    exec "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/run_webui.py" "\$@"
    ;;
esac
EOF

  chmod +x "$launcher_path"
  append_path_line "$rc_file"

  cat <<EOF

zaomeng is installed.

Install root: ${INSTALL_ROOT}
Launcher:     ${launcher_path}
Requirements: ${requirements_path}
Shell rc:     ${rc_file}

Next:
  Open a new shell, or run:
  export PATH="\$HOME/.local/bin:\$PATH"
  zaomeng

If your shell rc already contains unrelated broken lines and "source ${rc_file}" reports errors,
you can still start zaomeng right away with:
  ${launcher_path}

Useful:
  zaomeng web --reload
  zaomeng bump-web-assets
  zaomeng install-skill --skills-dir <your-skills-root>
EOF
}

main "$@"
