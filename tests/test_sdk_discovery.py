"""Exercise real CMake discovery and setup without requiring a compiler SDK."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SdkDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        for name in ("CMakeLists.txt", ".project_env"):
            shutil.copy2(ROOT / name, self.project / name)
        for name in ("scripts", "src"):
            shutil.copytree(ROOT / name, self.project / name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.settings = self.home / ".config/cwhip/settings.toml"
        self.build = self.project / "build"
        self.env = os.environ.copy()
        for name in (
            "CWHIP_SDK", "CMAKE_PREFIX_PATH", "Cwhip_DIR", "Cwhip_ROOT",
            "_PROJECT_NAME", "XDG_CONFIG_HOME",
        ):
            self.env.pop(name, None)
        self.env["HOME"] = str(self.home)
        self.fallback = self.make_sdk("fallback")
        self.env["CMAKE_PREFIX_PATH"] = str(self.fallback)
        self.shell_record = self.root / "shell-sdk.txt"
        tools = self.root / "tools"
        tools.mkdir()
        shell = tools / "bash"
        shell.write_text(
            '#!/bin/sh\nprintf "%s" "${CWHIP_SDK-}" > "$SHELL_RECORD"\n'
        )
        shell.chmod(0o755)
        self.env["PATH"] = f"{tools}:{self.env['PATH']}"
        self.env["SHELL_RECORD"] = str(self.shell_record)

    def make_sdk(self, name):
        prefix = self.root / name
        package = prefix / "lib/cmake/Cwhip"
        package.mkdir(parents=True)
        (package / "CwhipConfig.cmake").write_text(
            'get_filename_component(prefix "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)\n'
            'file(WRITE "${CMAKE_BINARY_DIR}/selected-sdk.txt" "${prefix}")\n'
            'set(Cwhip_APPLICATION_OUTPUT_DIRECTORIES TRUE)\n'
            'function(cwhip_add_program name)\n'
            '    add_custom_target("${name}")\n'
            '    set_target_properties("${name}" PROPERTIES\n'
            '        CWHIP_EXECUTABLE "${CMAKE_BINARY_DIR}/hello")\n'
            'endfunction()\n'
        )
        (package / "CwhipConfigVersion.cmake").write_text(
            'set(PACKAGE_VERSION "0.0.1")\n'
            'set(PACKAGE_VERSION_COMPATIBLE TRUE)\n'
            'set(PACKAGE_VERSION_EXACT TRUE)\n'
        )
        return prefix

    def write_settings(self, content):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(content)

    def select(self, prefix):
        self.write_settings(f"sdk_prefix = {json.dumps(str(prefix))}\n")

    def run_configure(self, setup=False, success=True, extra=(), shell_input=None):
        if setup:
            command = ["/bin/bash", str(self.project / "scripts/setup"), *extra]
        else:
            command = [
                "cmake", "-S", str(self.project), "-B", str(self.build), *extra,
            ]
        result = subprocess.run(
            command, cwd=self.root, env=self.env, capture_output=True, text=True,
            input=shell_input, timeout=60,
        )
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
            if setup:
                self.assertFalse(self.shell_record.exists(), output)
        return output

    def assert_selected(self, prefix):
        self.assertEqual((self.build / "selected-sdk.txt").read_text(), str(prefix))

    def test_missing_settings_preserves_prefix_discovery(self):
        self.run_configure(extra=("-DCMAKE_DISABLE_FIND_PACKAGE_Python3=TRUE",))
        self.assert_selected(self.fallback)
        self.assertFalse(self.settings.exists())

    def test_missing_key_preserves_cmake_dir_discovery(self):
        self.write_settings('[compiler]\nsdk_prefix = "/not/a/top-level/key"\n')
        self.env.pop("CMAKE_PREFIX_PATH")
        self.run_configure(extra=(
            f"-DCwhip_DIR={self.fallback / 'lib/cmake/Cwhip'}",
        ))
        self.assert_selected(self.fallback)

    def test_xdg_settings_win_over_home_settings(self):
        self.select(self.make_sdk("home-sdk"))
        home_settings = self.settings
        home_content = home_settings.read_bytes()
        config_home = self.root / 'XDG config with "quotes"'
        self.env["XDG_CONFIG_HOME"] = str(config_home) + "/"
        self.settings = config_home / "cwhip/settings.toml"
        prefix = self.make_sdk("xdg-sdk")
        self.select(prefix)
        xdg_content = self.settings.read_bytes()
        self.run_configure()
        self.assert_selected(prefix)
        self.run_configure(setup=True)
        self.assert_selected(prefix)
        self.assertEqual(self.shell_record.read_text(), str(prefix))
        self.assertEqual(home_settings.read_bytes(), home_content)
        self.assertEqual(self.settings.read_bytes(), xdg_content)

    def test_empty_xdg_uses_home_settings(self):
        self.env["XDG_CONFIG_HOME"] = ""
        prefix = self.make_sdk("home-sdk")
        self.select(prefix)
        self.run_configure()
        self.assert_selected(prefix)
        self.run_configure(setup=True)
        self.assert_selected(prefix)
        self.assertEqual(self.shell_record.read_text(), str(prefix))

    def test_missing_xdg_settings_do_not_fall_back_to_home_settings(self):
        self.write_settings("not valid TOML\n")
        self.env["XDG_CONFIG_HOME"] = str(self.root / "missing-config")
        self.run_configure()
        self.assert_selected(self.fallback)
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)
        self.assertEqual(self.shell_record.read_text(), "")

    def test_relative_xdg_is_rejected_unless_explicit_sdk_is_set(self):
        self.env["XDG_CONFIG_HOME"] = "relative-config"
        self.assertIn("not absolute", self.run_configure(success=False))
        self.assertIn("not absolute", self.run_configure(setup=True, success=False))
        self.env["CWHIP_SDK"] = str(self.fallback)
        self.run_configure()
        self.assert_selected(self.fallback)
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)

    def test_xdg_settings_work_without_home(self):
        self.env.pop("HOME")
        self.env["XDG_CONFIG_HOME"] = str(self.root / "xdg-config")
        self.settings = Path(self.env["XDG_CONFIG_HOME"]) / "cwhip/settings.toml"
        prefix = self.make_sdk("xdg-sdk")
        self.select(prefix)
        self.run_configure()
        self.assert_selected(prefix)
        self.run_configure(setup=True)
        self.assert_selected(prefix)

    def test_no_config_home_preserves_normal_discovery(self):
        self.env.pop("HOME")
        self.run_configure()
        self.assert_selected(self.fallback)
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)

    def test_settings_overrides_fallback_and_preserves_escaped_path(self):
        prefix = self.make_sdk('SDK with spaces and "quotes" ')
        self.select(prefix)
        before = self.settings.read_bytes()
        self.env["CWHIP_SDK"] = ""
        self.run_configure()
        self.assert_selected(prefix)
        self.assertEqual(self.settings.read_bytes(), before)

    def test_literal_toml_string_and_comments(self):
        prefix = self.make_sdk('literal "SDK"')
        self.write_settings(f"# installed SDK\nsdk_prefix = '{prefix}' # prefix\n")
        self.run_configure()
        self.assert_selected(prefix)

    def test_explicit_override_ignores_malformed_settings(self):
        self.write_settings('sdk_prefix = "unterminated\n')
        prefix = self.make_sdk("explicit")
        self.env["CWHIP_SDK"] = str(prefix)
        self.run_configure(extra=("-DCMAKE_DISABLE_FIND_PACKAGE_Python3=TRUE",))
        self.assert_selected(prefix)

    def test_explicit_override_wins_over_valid_settings_and_cmake_dir(self):
        self.select(self.make_sdk("settings-sdk"))
        prefix = self.make_sdk('explicit SDK "quotes"')
        self.env["CWHIP_SDK"] = str(prefix)
        self.env["Cwhip_DIR"] = str(self.fallback / "lib/cmake/Cwhip")
        self.run_configure()
        self.assert_selected(prefix)
        self.run_configure(setup=True)
        self.assert_selected(prefix)
        self.assertEqual(self.shell_record.read_text(), str(prefix))

    def test_explicit_invalid_prefix_does_not_fall_back(self):
        self.select(self.fallback)
        self.env["CWHIP_SDK"] = str(self.root / "missing")
        self.assertIn("Cwhip", self.run_configure(success=False))

    def test_invalid_settings_fail_instead_of_falling_back(self):
        invalid = (
            'sdk_prefix = "unterminated\n',
            "sdk_prefix = 42\n",
            'sdk_prefix = ""\n',
            'sdk_prefix = "relative/sdk"\n',
            f"sdk_prefix = {json.dumps(str(self.root / 'missing'))}\n",
            f"sdk_prefix = {json.dumps(str(self.project / 'CMakeLists.txt'))}\n",
        )
        for content in invalid:
            with self.subTest(content=content):
                self.write_settings(content)
                output = self.run_configure(success=False)
                self.assertIn("sdk_prefix", output)
                self.assertIn("settings.toml", output)

    def test_existing_non_sdk_directory_does_not_fall_back(self):
        self.select(self.home)
        self.assertIn("Cwhip", self.run_configure(success=False))

    def test_unreadable_settings_do_not_fall_back(self):
        self.select(self.fallback)
        self.settings.chmod(0)
        self.addCleanup(self.settings.chmod, 0o600)
        if os.access(self.settings, os.R_OK):
            self.skipTest("Current user can read mode-000 files")
        output = self.run_configure(success=False)
        self.assertIn("settings.toml", output)
        self.assertIn("sdk_prefix", output)
        self.run_configure(setup=True, success=False)

    def test_settings_directory_is_diagnosed(self):
        self.settings.mkdir(parents=True)
        self.assertIn("settings.toml", self.run_configure(success=False))
        self.assertIn("sdk_prefix", self.run_configure(setup=True, success=False))

    def test_changed_selection_replaces_cached_package(self):
        self.run_configure()
        prefix = self.make_sdk("settings-sdk")
        self.select(prefix)
        self.run_configure()
        self.assert_selected(prefix)
        explicit = self.make_sdk("explicit-sdk")
        self.env["CWHIP_SDK"] = str(explicit)
        self.run_configure()
        self.assert_selected(explicit)

    def test_setup_exports_settings_prefix_and_build_type(self):
        prefix = self.make_sdk('setup SDK "quotes" ')
        self.select(prefix)
        before = self.settings.read_bytes()
        self.run_configure(setup=True, extra=("release",))
        self.assert_selected(prefix)
        self.assertEqual(self.shell_record.read_text(), str(prefix))
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Release", (self.build / "CMakeCache.txt").read_text())
        self.assertEqual(self.settings.read_bytes(), before)

    def test_setup_real_shell_adds_settings_sdk_to_path(self):
        prefix = self.make_sdk('shell SDK with "quotes"')
        self.select(prefix)
        self.env["PATH"] = os.environ["PATH"]
        self.run_configure(
            setup=True,
            shell_input='printf "%s" "$PATH" > "$SHELL_RECORD"\nexit\n',
        )
        path_entries = self.shell_record.read_text().split(":")
        self.assertEqual(path_entries[:3], [
            str(self.project / "bin"),
            str(self.project / "scripts"),
            str(prefix / "bin"),
        ])
        self.assert_selected(prefix)

    def test_setup_explicit_override_ignores_bad_settings(self):
        self.write_settings("not valid TOML\n")
        self.env["CWHIP_SDK"] = str(self.fallback)
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)
        self.assertEqual(self.shell_record.read_text(), str(self.fallback))

    def test_setup_missing_settings_preserves_discovery(self):
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)
        self.assertEqual(self.shell_record.read_text(), "")
        self.assertFalse(self.settings.exists())

    def test_setup_missing_key_preserves_discovery(self):
        self.write_settings('other_setting = "value"\n')
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)
        self.assertEqual(self.shell_record.read_text(), "")

    def test_setup_bad_settings_never_opens_shell(self):
        self.write_settings('sdk_prefix = "relative"\n')
        output = self.run_configure(setup=True, success=False)
        self.assertIn("sdk_prefix", output)
        self.assertIn("project shell was not started", output)

    def test_setup_malformed_toml_never_opens_shell(self):
        self.write_settings('sdk_prefix = "unterminated\n')
        self.assertIn("sdk_prefix", self.run_configure(setup=True, success=False))

    def test_setup_invalid_override_never_falls_back(self):
        self.select(self.fallback)
        self.env["CWHIP_SDK"] = str(self.root / "missing")
        self.assertIn("CMake configuration failed", self.run_configure(setup=True, success=False))

    def test_setup_invalid_sdk_never_opens_shell(self):
        self.select(self.home)
        output = self.run_configure(setup=True, success=False)
        self.assertIn("CMake configuration failed", output)


if __name__ == "__main__":
    unittest.main()
