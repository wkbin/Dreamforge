from __future__ import annotations

import unittest
from pathlib import Path


class InstallScriptTests(unittest.TestCase):
    def test_install_script_can_try_auto_install_python_with_platform_package_manager(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_text = (repo_root / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("is_termux()", script_text)
        self.assertIn("auto_install_python()", script_text)
        self.assertIn('pkg install -y python', script_text)
        self.assertIn('apt-get install -y python3 python3-venv', script_text)
        self.assertIn('if auto_install_python; then', script_text)
        self.assertIn('pkg install python', script_text)
        self.assertIn('sudo apt-get install python3 python3-venv', script_text)

    def test_install_launcher_checks_remote_version_before_update(self):
        repo_root = Path(__file__).resolve().parents[1]
        script_text = (repo_root / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn('VERSION_FILE_RELATIVE="src/web/static/version.txt"', script_text)
        self.assertIn('STORAGE_ROOT="${ZAOMENG_STORAGE_DIR:-$HOME/.local/share/zaomeng-data}"', script_text)
        self.assertIn('fetch_remote_version()', script_text)
        self.assertIn('local_version="\\$(current_version || true)"', script_text)
        self.assertIn('remote_version="\\$(fetch_remote_version "\\${target_ref}" || true)"', script_text)
        self.assertIn('Local version / 本地版本:  \\${local_version}', script_text)
        self.assertIn('Remote version / 远端版本: \\${remote_version}', script_text)
        self.assertIn('if [ "\\${local_version}" = "\\${remote_version}" ]; then', script_text)
        self.assertIn('Update skipped / 跳过更新: zaomeng is already up to date.', script_text)
        self.assertIn('Update required / 需要更新: \\${local_version} -> \\${remote_version}', script_text)
        self.assertIn('Version check unavailable, proceeding with update.', script_text)
        self.assertIn('if [ ! -x "$launcher_path" ]; then', script_text)
        self.assertIn('Launcher creation failed / 启动命令创建失败', script_text)
        self.assertIn('export PATH="$HOME/.local/bin:$PATH"', script_text)
        self.assertIn('Data root / 数据目录:   ${STORAGE_ROOT}', script_text)
        self.assertIn('ZAOMENG_STORAGE_DIR="\\${STORAGE_ROOT}"', script_text)
        self.assertIn('"\\${INSTALL_ROOT}/scripts/run_webui.py" --storage-root "\\${STORAGE_ROOT}"', script_text)
        self.assertIn('exec "\\${PYTHON_BIN}" "\\${INSTALL_ROOT}/scripts/run_webui.py" --storage-root "\\${STORAGE_ROOT}" "\\$@"', script_text)


if __name__ == "__main__":
    unittest.main()
