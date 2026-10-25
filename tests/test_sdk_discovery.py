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
        for name in ("scripts", "src", "tests"):
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
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
            self.env[name] = str(self.home / name.lower())
        self.env["XDG_CONFIG_HOME"] = str(self.home / ".config")
        self.env["CWHIP_REGISTER_SDK"] = "OFF"
        self.fallback = self.make_sdk("fallback")
        self.env["CMAKE_PREFIX_PATH"] = str(self.fallback)
        self.shell_record = self.root / "shell-sdk.txt"
        tools = self.root / "tools"
        tools.mkdir()
        shell = tools / "bash"
        shell.write_text(
            '#!/bin/sh\n'
            'if [ "${1-}" != "--rcfile" ]; then exec /bin/bash "$@"; fi\n'
            'printf "%s" "${CWHIP_SDK-}" > "$SHELL_RECORD"\n'
            'printf "%s" "${CWHIP_BUILD_TYPE-}" > "$SHELL_BUILD_TYPE_RECORD"\n'
        )
        shell.chmod(0o755)
        self.env["PATH"] = f"{tools}:{self.env['PATH']}"
        self.env["SHELL_RECORD"] = str(self.shell_record)
        self.shell_build_type_record = self.root / "shell-build-type.txt"
        self.env["SHELL_BUILD_TYPE_RECORD"] = str(self.shell_build_type_record)

    def make_sdk(self, name, *, version="0.0.2", abi="numeric-v2"):
        prefix = self.root / name
        package = prefix / "lib/cmake/Cwhip"
        package.mkdir(parents=True)
        (package / "CwhipConfig.cmake").write_text(
            'get_filename_component(prefix "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)\n'
            'set(Cwhip_PREFIX "${prefix}")\n'
            'file(WRITE "${CMAKE_BINARY_DIR}/selected-sdk.txt" "${prefix}")\n'
            'set(Cwhip_APPLICATION_OUTPUT_DIRECTORIES TRUE)\n'
            'function(cwhip_add_program name)\n'
            '    add_custom_target("${name}")\n'
            '    set_target_properties("${name}" PROPERTIES\n'
            '        CWHIP_EXECUTABLE "${CMAKE_BINARY_DIR}/hello")\n'
            'endfunction()\n'
            'include("${CMAKE_CURRENT_LIST_DIR}/CwhipApplicationDefaults.cmake")\n'
            + (f'set(Cwhip_SDK_ABI "{abi}")\n' if abi is not None else "")
        )
        (package / "CwhipConfigVersion.cmake").write_text(
            f'set(PACKAGE_VERSION "{version}")\n'
            'if(PACKAGE_FIND_VERSION VERSION_EQUAL PACKAGE_VERSION)\n'
            '    set(PACKAGE_VERSION_COMPATIBLE TRUE)\n'
            '    set(PACKAGE_VERSION_EXACT TRUE)\n'
            'else()\n'
            '    set(PACKAGE_VERSION_COMPATIBLE FALSE)\n'
            '    set(PACKAGE_VERSION_EXACT FALSE)\n'
            'endif()\n'
        )
        install_prefix = self.root / "registered-install"
        (package / "CwhipApplicationDefaults.cmake").write_text(
            "function(cwhip_apply_application_defaults)\n"
            '    if(NOT DEFINED CMAKE_INSTALL_PREFIX AND "$ENV{CMAKE_INSTALL_PREFIX}" STREQUAL "")\n'
            f'        set(CMAKE_INSTALL_PREFIX "{install_prefix}" CACHE PATH "" FORCE)\n'
            "    endif()\n"
            "    get_property(build_type_cached CACHE CMAKE_BUILD_TYPE PROPERTY TYPE SET)\n"
            '    if(NOT build_type_cached AND NOT CMAKE_CONFIGURATION_TYPES AND (NOT DEFINED CMAKE_BUILD_TYPE OR "${CMAKE_BUILD_TYPE}" STREQUAL ""))\n'
            "        if(DEFINED ENV{CMAKE_BUILD_TYPE})\n"
            '            set(build_type_default "$ENV{CMAKE_BUILD_TYPE}")\n'
            "        else()\n"
            '            set(build_type_default "Release")\n'
            "        endif()\n"
            '        set(CMAKE_BUILD_TYPE "${build_type_default}" CACHE STRING "" FORCE)\n'
            '        set(CMAKE_BUILD_TYPE "${build_type_default}" PARENT_SCOPE)\n'
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

    def test_ctest_registers_sdk_executable(self):
        self.run_configure()
        tests = (self.build / "CTestTestfile.cmake").read_text()
        self.assertIn('add_test([=[hello]=]', tests)
        self.assertIn(f'"-DHELLO_EXECUTABLE={self.build}/hello"', tests)
        self.assertIn(f'"{self.project}/tests/check-hello.cmake"', tests)

    def test_ctest_can_be_disabled(self):
        self.run_configure(extra=("-DBUILD_TESTING=OFF",))
        self.assertFalse((self.build / "CTestTestfile.cmake").exists())

    def test_greeting_check_rejects_bad_output_and_exit_status(self):
        executable = self.root / "hello"
        for body, success in (
            ('printf "Hello, world!\\n"', True),
            ('printf "Hello, world!\\n"; exit 1', False),
            ('printf "wrong greeting\\n"', False),
            ('printf "Hello, world!\\n"; printf "error\\n" >&2', False),
        ):
            with self.subTest(body=body):
                executable.write_text(f"#!/bin/sh\n{body}\n")
                executable.chmod(0o755)
                result = subprocess.run(
                    ["cmake", f"-DHELLO_EXECUTABLE={executable}", "-P",
                     str(self.project / "tests/check-hello.cmake")],
                    cwd=self.root, env=self.env, capture_output=True,
                    text=True, timeout=30,
                )
                self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_incompatible_sdk_version_never_falls_back_or_opens_shell(self):
        self.run_configure()
        for version in ("0.0.1", "0.0.3"):
            prefix = self.make_sdk(f"version-{version}", version=version)
            self.env["CWHIP_SDK"] = str(prefix)
            for setup in (False, True):
                with self.subTest(version=version, setup=setup):
                    output = self.run_configure(setup=setup, success=False)
                    self.assertIn("0.0.2", output)
                    self.assertIn(str(prefix), output)
                    self.assert_selected(self.fallback)

    def test_incompatible_sdk_abi_never_falls_back_or_opens_shell(self):
        self.run_configure()
        for abi in (None, "", "legacy-v1"):
            prefix = self.make_sdk(f"abi-{abi}", abi=abi)
            self.env["CWHIP_SDK"] = str(prefix)
            for setup in (False, True):
                with self.subTest(abi=abi, setup=setup):
                    output = self.run_configure(setup=setup, success=False)
                    self.assertIn("incompatible SDK ABI", output)
                    self.assertIn("numeric-v2", output)
                    self.assertIn(str(prefix), output)
                    self.assertIn("Rebuild and reinstall", output)
                    self.assert_selected(prefix)

    def test_legacy_sdk_without_defaults_reports_actionable_error(self):
        package = self.fallback / "lib/cmake/Cwhip"
        config = package / "CwhipConfig.cmake"
        legacy_config = config.read_text().replace(
            'include("${CMAKE_CURRENT_LIST_DIR}/CwhipApplicationDefaults.cmake")\n',
            "",
        )
        (package / "CwhipApplicationDefaults.cmake").unlink()
        for selection in ("package-prefix", "explicit-prefix", "package-directory"):
            config.write_text(
                legacy_config if selection == "package-prefix" else
                legacy_config.replace('set(Cwhip_PREFIX "${prefix}")\n', "")
            )
            if selection == "explicit-prefix":
                self.env["CWHIP_SDK"] = str(self.fallback)
            else:
                self.env.pop("CWHIP_SDK", None)
            for setup in (False, True):
                with self.subTest(selection=selection, setup=setup):
                    output = self.run_configure(setup=setup, success=False)
                    self.assertIn(str(self.fallback), output)
                    self.assertIn("application-defaults capability", output)
                    self.assertIn("cwhip_apply_application_defaults()", output)
                    self.assertIn("Rebuild and reinstall an updated Cwhip SDK", output)
                    self.assertNotIn("Unknown CMake command", output)

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

    def test_explicit_empty_build_type_is_preserved(self):
        self.run_configure(extra=("-DCMAKE_BUILD_TYPE=",))
        self.assertIn(
            "CMAKE_BUILD_TYPE:STRING=\n",
            (self.build / "CMakeCache.txt").read_text(),
        )

    def test_existing_empty_build_type_cache_is_preserved(self):
        self.run_configure(extra=("-DCMAKE_BUILD_TYPE=",))
        self.run_configure()
        self.assertIn(
            "CMAKE_BUILD_TYPE:STRING=\n",
            (self.build / "CMakeCache.txt").read_text(),
        )

    def test_install_prefix_environment_override_is_preserved(self):
        install_prefix = self.root / "environment-install"
        self.env["CMAKE_INSTALL_PREFIX"] = str(install_prefix)
        self.env["CMAKE_BUILD_TYPE"] = "Debug"
        self.run_configure()
        cache = (self.build / "CMakeCache.txt").read_text()
        self.assertIn(f"CMAKE_INSTALL_PREFIX:PATH={install_prefix}", cache)
        self.assertIn("CMAKE_BUILD_TYPE:STRING=Debug", cache)

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

    def test_setup_clean_removes_outputs_before_configuring(self):
        for args, expected in (
            (("--clean",), "Release"),
            (("--clean", "debug"), "Debug"),
            (("debug", "--clean"), "Debug"),
            (("--clean", "release"), "Release"),
            (("release", "--clean"), "Release"),
            (("--clean", "profile"), "RelWithDebInfo"),
            (("profile", "--clean"), "RelWithDebInfo"),
        ):
            with self.subTest(args=args):
                self.run_configure(extra=("-DCMAKE_BUILD_TYPE=Debug",))
                for name in ("bin", "build", "lib", "doc/out", "share"):
                    directory = self.project / name
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / "stale-output").write_text("generated")
                source = (self.project / "src/main.cw").read_bytes()
                self.run_configure(setup=True, extra=args)
                self.assertTrue((self.build / "CMakeCache.txt").is_file())
                self.assertEqual(self.shell_build_type_record.read_text(), expected)
                for name in ("bin", "build", "lib", "doc/out", "share"):
                    self.assertFalse((self.project / name / "stale-output").exists())
                self.assertEqual((self.project / "src/main.cw").read_bytes(), source)
                self.assertTrue((self.project / "doc").is_dir())

    def test_setup_without_clean_keeps_existing_outputs(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.touch()
        self.run_configure(setup=True)
        self.assertTrue(marker.exists())

    def test_setup_clean_failure_stops_before_configuration(self):
        (self.project / "scripts/clean").write_text(
            '#!/bin/bash\nprintf "Cleanup failed\\n" >&2\nexit 7\n'
        )
        result = subprocess.run(
            ["/bin/bash", str(self.project / "scripts/setup"), "--clean"],
            cwd=self.root, env=self.env, capture_output=True, text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("Cleanup failed", result.stderr)
        self.assertFalse((self.build / "CMakeCache.txt").exists())
        self.assertFalse(self.shell_record.exists())

    def test_setup_usage_errors_do_not_clean_or_open_shell(self):
        self.build.mkdir()
        marker = self.build / "keep"
        marker.touch()
        for args in (
            ("--unknown",), ("invalid",), ("",), ("debug", "release"),
            ("--clean", "--clean"), ("--clean", "debug", "extra"),
            ("--clean", "--unknown"),
        ):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["/bin/bash", str(self.project / "scripts/setup"), *args],
                    cwd=self.root, env=self.env, capture_output=True, text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("[--clean] [debug|release|profile]", result.stderr)
                self.assertTrue(marker.exists())
                self.assertFalse(self.shell_record.exists())

    def test_setup_active_shell_guard_precedes_clean_and_argument_parsing(self):
        self.env["_PROJECT_NAME"] = "active-project"
        self.build.mkdir()
        marker = self.build / "keep"
        marker.touch()
        for args in (("--clean",), ("--clean", "--unknown")):
            result = subprocess.run(
                ["/bin/bash", str(self.project / "scripts/setup"), *args],
                cwd=self.root, env=self.env, capture_output=True, text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("already active", result.stderr)
            self.assertTrue(marker.exists())
            self.assertFalse(self.shell_record.exists())

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
