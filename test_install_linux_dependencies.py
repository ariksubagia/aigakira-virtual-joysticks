import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "install-linux-dependencies.sh"


class InstallerTests(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=10)

    def test_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_and_invalid_arguments(self):
        help_result = self.run_script("--help")
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("--check", help_result.stdout)
        invalid_result = self.run_script("--invalid")
        self.assertEqual(invalid_result.returncode, 2)
        self.assertIn("Usage:", invalid_result.stderr)

    def test_check_does_not_install(self):
        result = self.run_script("--check")
        self.assertIn(result.returncode, (0, 1))
        self.assertNotIn("Installing dependencies", result.stdout)
        self.assertIn("/dev/uinput", result.stdout + result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "installer would run the package manager directly as root")
    def test_install_invokes_sudo_without_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            sudo = Path(directory) / "sudo"
            sudo.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$INSTALLER_TEST_OUTPUT"\n')
            sudo.chmod(0o755)
            output = Path(directory) / "invocation"
            environment = dict(os.environ, PATH=directory + os.pathsep + os.environ.get("PATH", ""),
                               INSTALLER_TEST_OUTPUT=str(output))
            result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                                    timeout=10, env=environment)
            if "Unsupported distribution" in result.stderr:
                self.skipTest("package manager is not supported on this distribution")
            self.assertTrue(output.exists(), result.stderr)
            self.assertIn(output.read_text().split()[0], ("pacman", "apt-get", "dnf", "zypper"))


if __name__ == "__main__":
    unittest.main()