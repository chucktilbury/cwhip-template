"""Check project-shell build functions without a compiler SDK."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectShellTests(unittest.TestCase):
    def test_build_functions_preserve_arguments_status_and_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project with spaces"
            (project / "build").mkdir(parents=True)
            home = root / "home"
            home.mkdir()
            env = os.environ.copy()
            env.pop("_PROJECT_BUILD_DIR", None)
            env.update(
                HOME=str(home), _PROJECT_LOC=str(project),
                _PROJECT_NAME="test", _BUILD_TYPE="debug",
                CWHIP_REGISTER_SDK="OFF",
            )
            for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
                env[name] = str(home / name.lower())
            for command in ("build", "rebuild"):
                for targets in ([], ["hello"], ["target with spaces", "second"]):
                    for override in ("", str(root / "custom build")):
                        for status in (0, 7):
                            with self.subTest(
                                command=command, targets=targets,
                                override=override, status=status,
                            ):
                                result = subprocess.run(
                                    ["/bin/bash", "--noprofile", "--norc", "-c",
                                     'source "$1"\n'
                                     'cd "$HOME"\n'
                                     'cmake() { printf "%s\\0" "$@"; return "$MOCK_STATUS"; }\n'
                                     '"$2" "${@:3}"\n'
                                     'result=$?\n'
                                     'printf "shell-alive:%s\\0" "$result"\n'
                                     'exit "$result"\n',
                                     "shell-test", str(ROOT / ".project_env"),
                                     command, *targets],
                                    env={
                                        **env, "_PROJECT_BUILD_DIR": override,
                                        "MOCK_STATUS": str(status),
                                    },
                                    capture_output=True, timeout=30,
                                )
                                expected = [
                                    "--build", override or str(project / "build"),
                                    "--parallel", "12",
                                ]
                                if command == "rebuild":
                                    expected.append("--clean-first")
                                if targets:
                                    expected.extend(["--target", *targets])
                                expected.append(f"shell-alive:{status}")
                                self.assertEqual(result.returncode, status, result.stderr)
                                self.assertEqual(
                                    result.stdout.decode().split("\0")[:-1],
                                    expected,
                                )

    def test_build_scripts_removed_and_clean_retained(self):
        for name in ("build", "rebuild"):
            self.assertFalse((ROOT / "scripts" / name).exists())
        self.assertTrue(os.access(ROOT / "scripts/clean", os.X_OK))


if __name__ == "__main__":
    unittest.main()
