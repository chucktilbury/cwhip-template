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
        self.sdk_config = self.settings.with_name("sdk.toml")
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
            '#!/bin/sh\n'
            'printf "%s" "${CWHIP_SDK-}" > "$SHELL_RECORD"\n'
            'printf "%s" "${CWHIP_BUILD_TYPE-}" > "$SHELL_BUILD_TYPE_RECORD"\n'
        )
        shell.chmod(0o755)
        self.env["PATH"] = f"{tools}:{self.env['PATH']}"
        self.env["SHELL_RECORD"] = str(self.shell_record)
        self.shell_build_type_record = self.root / "shell-build-type.txt"
        self.env["SHELL_BUILD_TYPE_RECORD"] = str(self.shell_build_type_record)

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
            'include("${CMAKE_CURRENT_LIST_DIR}/CwhipApplicationDefaults.cmake")\n'
        )
        (package / "CwhipConfigVersion.cmake").write_text(
            'set(PACKAGE_VERSION "0.0.1")\n'
            'set(PACKAGE_VERSION_COMPATIBLE TRUE)\n'
            'set(PACKAGE_VERSION_EXACT TRUE)\n'
        )
        install_prefix = self.root / "registered-install"
        (package / "CwhipApplicationDefaults.cmake").write_text(
            "function(cwhip_apply_application_defaults)\n"
            "    if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)\n"
            f'        set(CMAKE_INSTALL_PREFIX "{install_prefix}" CACHE PATH "" FORCE)\n'
            "    endif()\n"
            '    if(NOT DEFINED CMAKE_BUILD_TYPE OR CMAKE_BUILD_TYPE STREQUAL "")\n'
            '        set(CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE)\n'
            "    endif()\n"
            "endfunction()\n"
        )
        return prefix

    def write_settings(self, content):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(content)

    def select(self, prefix):
        self.write_settings(f"sdk_prefix = {json.dumps(str(prefix))}\n")

    def write_sdk_config(self, content):
        self.sdk_config.parent.mkdir(parents=True, exist_ok=True)
        self.sdk_config.write_text(content)

    def select_sdk(self, prefix):
        self.write_sdk_config(f"sdk_prefix = {json.dumps(str(prefix))}\n")

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

    def test_application_defaults_seed_install_prefix_and_build_type(self):
        self.run_configure()
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn(f"CMAKE_INSTALL_PREFIX:PATH={self.root}/registered-install", cache)
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Release", cache)

    def test_explicit_cmake_settings_override_application_defaults(self):
        install_prefix = self.root / "explicit-install"
        self.run_configure(extra=(
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        ))
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn("CMAKE_BUILD_TYPE:STRING=RelWithDebInfo", cache)
        self.assertIn(f"CMAKE_INSTALL_PREFIX:PATH={install_prefix}", cache)

    def test_existing_cache_settings_override_application_defaults(self):
        install_prefix = self.root / "cached-install"
        self.run_configure(extra=(
            "-DCMAKE_BUILD_TYPE=Debug",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
        ))
        self.run_configure()
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Debug", cache)
        self.assertIn(f"CMAKE_INSTALL_PREFIX:PATH={install_prefix}", cache)

    def test_setup_implicit_build_type_uses_application_default(self):
        self.run_configure(setup=True)
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Release", cache)
        self.assertEqual(self.shell_build_type_record.read_text(), "Release")

    def test_setup_explicit_build_type_overrides_application_default(self):
        self.run_configure(setup=True, extra=("profile",))
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn("CMAKE_BUILD_TYPE:STRING=RelWithDebInfo", cache)
        self.assertEqual(self.shell_build_type_record.read_text(), "RelWithDebInfo")

    def test_setup_without_argument_preserves_existing_build_type(self):
        self.run_configure(extra=("-DCMAKE_BUILD_TYPE=Debug",))
        self.run_configure(setup=True)
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Debug", cache)
        self.assertEqual(self.shell_build_type_record.read_text(), "Debug")

    def test_sdk_config_survives_preferences_rewrite(self):
        prefix = self.make_sdk('dedicated SDK with "quotes" ')
        self.select_sdk(prefix)
        before = self.sdk_config.read_bytes()
        for preferences in (
            f"sdk_prefix = {json.dumps(str(self.fallback))}\n",
            '[editor]\ntheme = "dark"\n',
            "not valid TOML\n",
        ):
            with self.subTest(preferences=preferences):
                self.write_settings(preferences)
                for setup in (False, True):
                    self.run_configure(setup=setup)
                    self.assert_selected(prefix)
                    if setup:
                        self.assertEqual(self.shell_record.read_text(), str(prefix))
                self.assertEqual(self.sdk_config.read_bytes(), before)
                self.assertEqual(self.settings.read_text(), preferences)

    def test_sdk_config_missing_key_never_uses_legacy(self):
        self.select(self.make_sdk("legacy"))
        for content in ("", '[compiler]\nsdk_prefix = "/not/top-level"\n'):
            with self.subTest(content=content):
                self.write_sdk_config(content)
                for setup in (False, True):
                    self.run_configure(setup=setup)
                    self.assert_selected(self.fallback)
                    if setup:
                        self.assertEqual(self.shell_record.read_text(), "")

    def test_invalid_sdk_config_never_uses_legacy_or_cached_package(self):
        self.select(self.fallback)
        self.run_configure()
        invalid = (
            'sdk_prefix = "unterminated\n',
            "sdk_prefix = 42\n",
            'sdk_prefix = ""\n',
            'sdk_prefix = "relative/sdk"\n',
            'sdk_prefix = "/bad\\u0000path"\n',
            'sdk_prefix = "/bad\\npath"\n',
            'sdk_prefix = "/bad\\rpath"\n',
            f"sdk_prefix = {json.dumps(str(self.root / 'missing'))}\n",
            f"sdk_prefix = {json.dumps(str(self.project / 'CMakeLists.txt'))}\n",
            f"sdk_prefix = {json.dumps(str(self.fallback))}\nsdk_prefix = 'duplicate'\n",
        )
        for content in invalid:
            with self.subTest(content=content):
                self.write_sdk_config(content)
                for setup in (False, True):
                    output = self.run_configure(setup=setup, success=False)
                    self.assertIn("sdk.toml", output)
                    self.assertIn("sdk_prefix", output)

    def test_sdk_config_directory_or_broken_symlink_is_diagnosed(self):
        self.select(self.fallback)
        self.sdk_config.mkdir()
        for setup in (False, True):
            self.assertIn("sdk.toml", self.run_configure(setup=setup, success=False))
        self.sdk_config.rmdir()
        self.sdk_config.symlink_to(self.root / "missing-config")
        for setup in (False, True):
            self.assertIn("sdk.toml", self.run_configure(setup=setup, success=False))

    def test_unreadable_sdk_config_never_uses_legacy(self):
        self.select(self.fallback)
        self.select_sdk(self.fallback)
        self.sdk_config.chmod(0)
        self.addCleanup(self.sdk_config.chmod, 0o600)
        if os.access(self.sdk_config, os.R_OK):
            self.skipTest("Current user can read mode-000 files")
        for setup in (False, True):
            self.assertIn("sdk.toml", self.run_configure(setup=setup, success=False))

    def test_sdk_config_xdg_root_is_exclusive(self):
        self.select_sdk(self.make_sdk("home-sdk"))
        self.select(self.make_sdk("home-legacy"))
        self.env["XDG_CONFIG_HOME"] = str(self.root / "XDG config with spaces") + "/"
        self.sdk_config = Path(self.env["XDG_CONFIG_HOME"]) / "cwhip/sdk.toml"
        for setup in (False, True):
            self.run_configure(setup=setup)
            self.assert_selected(self.fallback)
        prefix = self.make_sdk("xdg-sdk")
        self.select_sdk(prefix)
        for setup in (False, True):
            self.run_configure(setup=setup)
            self.assert_selected(prefix)
            if setup:
                self.assertEqual(self.shell_record.read_text(), str(prefix))

    def test_sdk_config_replaces_stale_cache_without_default_fallback(self):
        self.run_configure()
        prefix = self.make_sdk("dedicated-sdk")
        self.select_sdk(prefix)
        for setup in (False, True):
            self.run_configure(setup=setup)
            self.assert_selected(prefix)
        self.shell_record.unlink()
        self.select_sdk(self.home)
        for setup in (False, True):
            self.assertIn("Cwhip", self.run_configure(setup=setup, success=False))

    def test_override_bypasses_both_config_files(self):
        self.write_settings("not valid TOML\n")
        self.write_sdk_config('sdk_prefix = ""\n')
        self.env["CWHIP_SDK"] = str(self.fallback)
        self.run_configure(extra=("-DCMAKE_DISABLE_FIND_PACKAGE_Python3=TRUE",))
        self.assert_selected(self.fallback)
        self.run_configure(setup=True)
        self.assert_selected(self.fallback)
        self.assertEqual(self.shell_record.read_text(), str(self.fallback))

    def test_empty_override_and_xdg_allow_dedicated_literal_string(self):
        self.env["CWHIP_SDK"] = ""
        self.env["XDG_CONFIG_HOME"] = ""
        prefix = self.make_sdk('literal SDK "quotes"')
        self.write_sdk_config(f"# dedicated SDK\nsdk_prefix = '{prefix}' # prefix\n")
        for setup in (False, True):
            self.run_configure(setup=setup)
            self.assert_selected(prefix)
            if setup:
                self.assertEqual(self.shell_record.read_text(), str(prefix))

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

    def test_setup_real_shell_adds_dedicated_sdk_to_path(self):
        prefix = self.make_sdk('shell SDK with "quotes"')
        self.select_sdk(prefix)
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
