"""Opt-in end-to-end checks against a read-only installed numeric-v2 SDK."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("CWHIP_TEST_SDK"), "Set CWHIP_TEST_SDK to test a real SDK")
class SdkIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.sdk = Path(os.environ["CWHIP_TEST_SDK"]).resolve(strict=True)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = os.environ.copy()
        for name in (
            "CMAKE_PREFIX_PATH", "Cwhip_DIR", "Cwhip_ROOT", "CWHIP_MODULE_DIR",
            "CWHIP_PACKAGE_PATH", "CWHIP_MODULE_REGISTRY", "DESTDIR",
            "XDG_RUNTIME_DIR", "CMAKE_BUILD_TYPE", "CMAKE_INSTALL_PREFIX",
        ):
            self.env.pop(name, None)
        for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
            directory = self.root / name.lower()
            directory.mkdir()
            self.env[name] = str(directory)
        self.env.update(
            CWHIP_SDK=str(self.sdk),
            CWHIP_HOME=str(self.sdk),
            CWHIP_STDLIB_MODULE_DIR=str(self.sdk / "share/cwhip/modules"),
            PYTHONDONTWRITEBYTECODE="1",
        )

    def run_command(self, *command, success=True):
        result = subprocess.run(
            command, cwd=self.root, env=self.env, capture_output=True,
            text=True, timeout=180,
        )
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
        return result

    def test_template_build_install_and_generated_metadata(self):
        project = self.root / "project"
        project.mkdir()
        shutil.copy2(ROOT / "CMakeLists.txt", project)
        for name in ("src", "scripts"):
            shutil.copytree(ROOT / name, project / name)
        build = self.root / "build"
        install = self.root / "install"
        output = self.root / "output"
        self.run_command(
            "cmake", "-S", str(project), "-B", str(build),
            "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={install}",
            f"-DCWHIP_BIN_DIR={output / 'bin'}", f"-DCWHIP_LIB_DIR={output / 'lib'}",
        )
        self.run_command("cmake", "--build", str(build), "--parallel", "2")
        self.run_command("cmake", "--install", str(build))
        for executable in (output / "bin/hello", install / "bin/hello"):
            result = self.run_command(str(executable))
            self.assertEqual(result.stdout, "Hello, world!\n")
            self.assertEqual(result.stderr, "")
        self.assertFalse((project / "bin").exists())
        self.assertFalse((project / "lib").exists())
        generated = build / "hello-project"
        self.assertTrue((generated / "cwhip-pkg.toml").is_file())
        lock = tomllib.loads((generated / "cwhip-pkg.lock").read_text())
        self.assertTrue(lock["packages"])
        for name, package in lock["packages"].items():
            self.assertEqual(package["repo"], "builtin")
            manifest = self.sdk / "share/cwhip/modules" / name / package["version"] / "cwhip-package.toml"
            document = tomllib.loads(manifest.read_text())
            self.assertEqual(document["package"]["sdk-abi"], "numeric-v2")

    def test_package_tool_rejects_missing_and_stale_abi(self):
        modules = self.root / "modules"
        package = modules / "math/0.1.0"
        shutil.copytree(self.sdk / "share/cwhip/modules/math/0.1.0", package)
        manifest = package / "cwhip-package.toml"
        original = manifest.read_text()
        self.assertIn('sdk-abi = "numeric-v2"', original)
        self.env["CWHIP_STDLIB_MODULE_DIR"] = str(modules)
        for abi in (None, "legacy-v1"):
            with self.subTest(abi=abi):
                replacement = "" if abi is None else f'sdk-abi = "{abi}"'
                manifest.write_text(original.replace('sdk-abi = "numeric-v2"', replacement))
                project = self.root / f"rejected-{abi}"
                project.mkdir()
                result = self.run_command(
                    sys.executable, str(self.sdk / "bin/cwhip-pkg"),
                    "init", str(project), success=False,
                )
                output = result.stdout + result.stderr
                self.assertIn("error[PKG2004]", output)
                self.assertIn("incompatible package SDK ABI", output)
                self.assertIn("numeric-v2", output)
                self.assertFalse((project / "cwhip-pkg.toml").exists())
                self.assertFalse((project / "cwhip-pkg.lock").exists())


if __name__ == "__main__":
    unittest.main()
