#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${ZAOMENG_REPO_SLUG:-wkbin/zaomeng}"
REPO_REF="${ZAOMENG_REF:-main}"
INSTALL_ROOT="${ZAOMENG_INSTALL_DIR:-$HOME/.local/share/zaomeng}"
STORAGE_ROOT="${ZAOMENG_STORAGE_DIR:-$HOME/.local/share/zaomeng-data}"
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
    echo "Missing required command / 缺少必要命令: $1" >&2
    exit 1
  fi
}

is_termux() {
  [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux/files/usr" ]
}

install_system_packages() {
  if [ "$#" -eq 0 ]; then
    return 0
  fi

  if is_termux; then
    if command -v pkg >/dev/null 2>&1; then
      echo "Installing packages in Termux via pkg / 正在通过 pkg 安装依赖: $*" >&2
      pkg update -y >&2
      pkg install -y "$@" >&2
      return
    fi
    echo "Termux was detected but pkg is unavailable. / 检测到 Termux，但没有找到 pkg。" >&2
    return 1
  fi

  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing packages via apt-get / 正在通过 apt-get 安装依赖: $*" >&2
    run_pkg_manager "apt-get update -y && apt-get install -y $*"
    return
  fi
  if command -v apt >/dev/null 2>&1; then
    echo "Installing packages via apt / 正在通过 apt 安装依赖: $*" >&2
    run_pkg_manager "apt update -y && apt install -y $*"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    echo "Installing packages via dnf / 正在通过 dnf 安装依赖: $*" >&2
    run_pkg_manager "dnf install -y $*"
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    echo "Installing packages via yum / 正在通过 yum 安装依赖: $*" >&2
    run_pkg_manager "yum install -y $*"
    return
  fi
  if command -v pacman >/dev/null 2>&1; then
    echo "Installing packages via pacman / 正在通过 pacman 安装依赖: $*" >&2
    run_pkg_manager "pacman -Sy --noconfirm $*"
    return
  fi
  if command -v zypper >/dev/null 2>&1; then
    echo "Installing packages via zypper / 正在通过 zypper 安装依赖: $*" >&2
    run_pkg_manager "zypper --non-interactive install $*"
    return
  fi
  if command -v apk >/dev/null 2>&1; then
    echo "Installing packages via apk / 正在通过 apk 安装依赖: $*" >&2
    run_pkg_manager "apk add --no-cache $*"
    return
  fi

  echo "No supported package manager was found for: $* / 未找到可用于安装以下依赖的包管理器: $*" >&2
  return 1
}

auto_install_base_tools() {
  local missing_tools=()

  if ! command -v tar >/dev/null 2>&1; then
    missing_tools+=("tar")
  fi
  if ! command -v mktemp >/dev/null 2>&1 || ! command -v chmod >/dev/null 2>&1; then
    missing_tools+=("coreutils")
  fi
  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    missing_tools+=("curl" "wget")
  fi
  if ! command -v git >/dev/null 2>&1; then
    missing_tools+=("git")
  fi

  if [ "${#missing_tools[@]}" -eq 0 ]; then
    return 0
  fi

  echo "Trying to install base CLI tools... / 正在尝试自动安装基础命令行工具..." >&2
  install_system_packages "${missing_tools[@]}"
}

run_pkg_manager() {
  local install_cmd="$1"
  if [ "$(id -u)" -eq 0 ]; then
    sh -c "$install_cmd"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo sh -c "$install_cmd"
    return
  fi
  echo "Need elevated privileges to install dependencies / 安装依赖需要更高权限: $install_cmd" >&2
  return 1
}

auto_install_python() {
  echo "Python 3 was not found. Trying to install it automatically... / 未检测到 Python 3，正在尝试自动安装..." >&2

  if is_termux; then
    install_system_packages python
    return
  fi

  if command -v apt-get >/dev/null 2>&1 || command -v apt >/dev/null 2>&1; then
    install_system_packages python3 python3-venv
    return
  fi
  if command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1 || command -v zypper >/dev/null 2>&1; then
    install_system_packages python3
    return
  fi
  if command -v pacman >/dev/null 2>&1; then
    install_system_packages python
    return
  fi
  if command -v apk >/dev/null 2>&1; then
    install_system_packages python3 py3-pip
    return
  fi

  echo "Python 3 is required but no supported package manager was found. / 需要 Python 3，但没有找到可自动安装的包管理器。" >&2
  return 1
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

  if auto_install_python; then
    if command -v python3 >/dev/null 2>&1; then
      echo python3
      return
    fi
    if command -v python >/dev/null 2>&1; then
      echo python
      return
    fi
  fi

  if is_termux; then
    echo "Python 3 is required. Please run: pkg install python / 需要 Python 3，请执行：pkg install python" >&2
  elif command -v apt-get >/dev/null 2>&1 || command -v apt >/dev/null 2>&1; then
    echo "Python 3 is required. Please run: sudo apt-get install python3 python3-venv / 需要 Python 3，请执行：sudo apt-get install python3 python3-venv" >&2
  else
    echo "Python 3 is required. Please install python3 first. / 需要 Python 3，请先安装 python3。" >&2
  fi
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
  echo "curl or wget was not found. Trying to install a downloader... / 未检测到 curl 或 wget，正在尝试自动安装下载工具..." >&2
  if auto_install_base_tools; then
    if command -v curl >/dev/null 2>&1; then
      echo curl
      return
    fi
    if command -v wget >/dev/null 2>&1; then
      echo wget
      return
    fi
  fi
  echo "curl or wget is required. / 需要安装 curl 或 wget。" >&2
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
  auto_install_base_tools || true
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
  local legacy_storage_root="${INSTALL_ROOT}/.zaomeng-web"
  local storage_backup_path="${TMP_DIR}/zaomeng-storage-backup"
  local extracted_dir
  local rc_file
  rc_file="$(detect_rc_file)"

  mkdir -p "$extract_root" "$BIN_DIR" "$(dirname "$INSTALL_ROOT")" "$(dirname "$STORAGE_ROOT")"

  echo "Downloading / 正在下载: ${archive_url}"
  if ! fetch_archive "$archive_url" "$archive_path" "$fetcher"; then
    echo "Failed to download ${archive_url}. Please check your network connection and try again. / 下载失败，请检查网络后重试。" >&2
    exit 1
  fi

  if [ -d "$legacy_storage_root" ] && [ ! -e "$STORAGE_ROOT" ]; then
    mv "$legacy_storage_root" "$storage_backup_path"
  fi
  rm -rf "$INSTALL_ROOT"
  tar -xzf "$archive_path" -C "$extract_root"
  extracted_dir="$(find "$extract_root" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [ -z "$extracted_dir" ]; then
    echo "Failed to locate extracted repository directory. / 未找到解压后的仓库目录。" >&2
    exit 1
  fi
  mv "$extracted_dir" "$INSTALL_ROOT"
  if [ -d "$storage_backup_path" ] && [ ! -e "$STORAGE_ROOT" ]; then
    mv "$storage_backup_path" "$STORAGE_ROOT"
  fi
  mkdir -p "$STORAGE_ROOT"

  if [ ! -f "$requirements_path" ]; then
    echo "Missing runtime requirements file / 缺少运行时依赖文件: ${requirements_path}" >&2
    exit 1
  fi

  echo "Creating virtual environment / 正在创建虚拟环境"
  "$python_cmd" -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install --upgrade pip setuptools wheel
  "$venv_dir/bin/python" -m pip install -r "$requirements_path"

  cat >"$launcher_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT}"
STORAGE_ROOT="${STORAGE_ROOT}"
BUILTIN_NOVELS_ROOT="\${INSTALL_ROOT}/builtin_novels"
PYTHON_BIN="\${INSTALL_ROOT}/.venv/bin/python"
INSTALL_PYTHON="${python_cmd}"
REPO_SLUG="${REPO_SLUG}"
REPO_REF="${REPO_REF}"
BIN_DIR="${BIN_DIR}"
RC_FILE="${rc_file}"
RUNTIME_REQUIREMENTS_FILE="${RUNTIME_REQUIREMENTS_FILE}"
INSTALLER_URL="https://raw.githubusercontent.com/${REPO_SLUG}/${REPO_REF}/scripts/install.sh"
VERSION_FILE_RELATIVE="src/web/static/version.txt"

if [ ! -x "\${PYTHON_BIN}" ]; then
  echo "zaomeng runtime is missing / 缺少 zaomeng 运行时: \${PYTHON_BIN}" >&2
  exit 1
fi

run_webui() {
  env ZAOMENG_WEB_BUILTIN_NOVELS_ROOT="\${BUILTIN_NOVELS_ROOT}" \
    "\${PYTHON_BIN}" "\${INSTALL_ROOT}/scripts/run_webui.py" --storage-root "\${STORAGE_ROOT}" "\$@"
}

current_version() {
  local version_file="\${INSTALL_ROOT}/\${VERSION_FILE_RELATIVE}"
  if [ ! -f "\${version_file}" ]; then
    return 1
  fi
  tr -d '\r' < "\${version_file}" | head -n 1
}

download_text() {
  local url="\${1:-}"
  if [ -z "\${url}" ]; then
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location "\${url}"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "\${url}"
    return
  fi
  return 1
}

fetch_remote_version() {
  local target_ref="\${1:-\${REPO_REF}}"
  local version_url="https://raw.githubusercontent.com/\${REPO_SLUG}/\${target_ref}/\${VERSION_FILE_RELATIVE}"
  download_text "\${version_url}" | tr -d '\r' | head -n 1
}

run_update() {
  local target_ref="\${1:-\${REPO_REF}}"
  local installer_url="https://raw.githubusercontent.com/\${REPO_SLUG}/\${target_ref}/scripts/install.sh"
  local local_version=""
  local remote_version=""

  local_version="\$(current_version || true)"
  remote_version="\$(fetch_remote_version "\${target_ref}" || true)"

  if [ -n "\${local_version}" ] && [ -n "\${remote_version}" ]; then
    echo "Local version / 本地版本:  \${local_version}"
    echo "Remote version / 远端版本: \${remote_version}"
    if [ "\${local_version}" = "\${remote_version}" ]; then
      echo "Update skipped / 跳过更新: zaomeng is already up to date."
      echo "zaomeng 已是最新版本，无需更新。"
      return 0
    fi
    echo "Update required / 需要更新: \${local_version} -> \${remote_version}"
    echo "Updating zaomeng / 正在更新 zaomeng: \${local_version} -> \${remote_version} (\${REPO_SLUG}@\${target_ref})"
  else
    echo "Updating zaomeng / 正在更新 zaomeng: \${REPO_SLUG}@\${target_ref}"
    echo "Version check unavailable, proceeding with update. / 暂时无法比对版本，继续执行更新。"
  fi

  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location "\${installer_url}" | \
      env \
        ZAOMENG_REPO_SLUG="\${REPO_SLUG}" \
        ZAOMENG_REF="\${target_ref}" \
        ZAOMENG_INSTALL_DIR="\${INSTALL_ROOT}" \
        ZAOMENG_STORAGE_DIR="\${STORAGE_ROOT}" \
        ZAOMENG_BIN_DIR="\${BIN_DIR}" \
        ZAOMENG_PYTHON="\${INSTALL_PYTHON}" \
        ZAOMENG_REQUIREMENTS_FILE="\${RUNTIME_REQUIREMENTS_FILE}" \
        bash
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "\${installer_url}" | \
      env \
        ZAOMENG_REPO_SLUG="\${REPO_SLUG}" \
        ZAOMENG_REF="\${target_ref}" \
        ZAOMENG_INSTALL_DIR="\${INSTALL_ROOT}" \
        ZAOMENG_STORAGE_DIR="\${STORAGE_ROOT}" \
        ZAOMENG_BIN_DIR="\${BIN_DIR}" \
        ZAOMENG_PYTHON="\${INSTALL_PYTHON}" \
        ZAOMENG_REQUIREMENTS_FILE="\${RUNTIME_REQUIREMENTS_FILE}" \
        bash
    return
  fi
  echo "curl or wget is required for update. / 更新需要 curl 或 wget。" >&2
  exit 1
}

remove_path_line() {
  local rc_target="\${1:-}"
  local path_line='export PATH="$HOME/.local/bin:$PATH"'
  [ -n "\${rc_target}" ] || return 0
  [ -f "\${rc_target}" ] || return 0
  local temp_file
  temp_file="\$(mktemp)"
  if ! grep -Fvx "\${path_line}" "\${rc_target}" > "\${temp_file}"; then
    : > "\${temp_file}"
  fi
  mv "\${temp_file}" "\${rc_target}"
}

run_uninstall() {
  echo "Uninstalling zaomeng / 正在卸载 zaomeng"
  remove_path_line "\${RC_FILE}"
  rm -rf "\${INSTALL_ROOT}"
  rm -rf "\${STORAGE_ROOT}"
  rm -f "\${BIN_DIR}/zaomeng"
  cat <<MSG
zaomeng has been removed.
zaomeng 已卸载完成。

Removed install root / 已删除安装目录: \${INSTALL_ROOT}
Removed data root / 已删除数据目录: \${STORAGE_ROOT}
Removed launcher / 已删除启动命令: \${BIN_DIR}/zaomeng
Updated shell rc / 已更新 shell 配置: \${RC_FILE}

If your current shell still has the old PATH cached, open a new shell.
如果你当前 shell 里还保留旧 PATH，重新打开一个 shell 即可。
MSG
}

if [ \$# -eq 0 ]; then
  run_webui
fi

case "\$1" in
  uninstall)
    shift
    run_uninstall
    ;;
  update)
    shift
    run_update "\${1:-}"
    ;;
  web)
    shift
    run_webui "\$@"
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
zaomeng commands / 可用命令:
  zaomeng                Start the Web UI on 127.0.0.1:8000 / 启动 Web UI
  zaomeng uninstall      Remove the installed runtime and launcher / 卸载已安装的运行环境和启动命令
  zaomeng update [ref]   Reinstall from the current source or target ref / 从当前来源或指定 ref 重新安装更新
  zaomeng web [args]     Forward args to scripts/run_webui.py / 转发参数给 run_webui.py
  zaomeng bump-web-assets [version]
                         Bump or explicitly sync the static asset version / 更新或同步静态资源版本号
  zaomeng install-skill [args]
                         Forward args to scripts/install_skill.py / 转发参数给 install_skill.py
  zaomeng version        Print the current web static asset version / 输出当前静态资源版本
HELP
    ;;
  *)
    run_webui "\$@"
    ;;
esac
EOF

  chmod +x "$launcher_path"
  if [ ! -x "$launcher_path" ]; then
    echo "Launcher creation failed / 启动命令创建失败: ${launcher_path}" >&2
    exit 1
  fi
  append_path_line "$rc_file"

cat <<EOF

zaomeng is installed.
zaomeng 已安装完成。

Install root / 安装目录: ${INSTALL_ROOT}
Data root / 数据目录:   ${STORAGE_ROOT}
Launcher / 启动命令:     ${launcher_path}
Requirements / 依赖文件: ${requirements_path}
Shell rc / Shell 配置:  ${rc_file}

Next / 下一步:
  Open a new shell, or run / 打开一个新的 shell，或执行：
  export PATH="$HOME/.local/bin:$PATH"
  zaomeng

If your shell rc already contains unrelated broken lines and "source ${rc_file}" reports errors,
如果你的 shell 配置里本来就有其他错误，导致 "source ${rc_file}" 报错，
you can still start zaomeng right away with / 你仍然可以直接这样启动：
  ${launcher_path}

Useful / 常用命令:
  zaomeng uninstall
  zaomeng update
  zaomeng web --reload
  zaomeng bump-web-assets
  zaomeng install-skill --skills-dir <your-skills-root>
EOF
}

main "$@"
