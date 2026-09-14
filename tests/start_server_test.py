import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_start_server():
    core_module = types.ModuleType("core")
    core_module.__path__ = []
    server_module = types.ModuleType("core.server")
    server_module.__path__ = []
    app_module = types.ModuleType("core.server.app")
    app_module.CapsWriterServer = object

    spec = importlib.util.spec_from_file_location(
        "capswriter_start_server_test", ROOT / "start_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    fake_modules = {
        "core": core_module,
        "core.server": server_module,
        "core.server.app": app_module,
    }
    with patch.dict(sys.modules, fake_modules):
        spec.loader.exec_module(module)
    return module


start_server = load_start_server()


class StartServerCliTests(unittest.TestCase):
    def cli_api(self):
        self.assertTrue(
            hasattr(start_server, "parse_server_args")
            and hasattr(start_server, "configure_model"),
            "start_server must expose model-selection CLI helpers",
        )
        return start_server.parse_server_args, start_server.configure_model

    def test_default_keeps_configured_model(self):
        parse_server_args, configure_model = self.cli_api()
        original = start_server.ServerConfig.model_type

        args = parse_server_args([])
        configure_model(args.model)

        self.assertEqual(start_server.ServerConfig.model_type, original)

    def test_all_supported_models_can_be_selected(self):
        parse_server_args, configure_model = self.cli_api()
        original = start_server.ServerConfig.model_type

        try:
            for model_type in start_server.SUPPORTED_MODELS:
                with self.subTest(model_type=model_type):
                    args = parse_server_args(["--model", model_type])
                    configure_model(args.model)
                    self.assertEqual(start_server.ServerConfig.model_type, model_type)
        finally:
            start_server.ServerConfig.model_type = original

    def test_unknown_model_is_rejected(self):
        parse_server_args, _ = self.cli_api()

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_server_args(["--model", "unknown"])


if __name__ == "__main__":
    unittest.main()
