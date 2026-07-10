import unittest


class RuntimeImportRegressionTests(unittest.TestCase):
    def test_runtime_entrypoint_imports(self) -> None:
        from src import main
        from src.core.signal_engine import evaluate_symbol

        self.assertTrue(callable(main.main))
        self.assertTrue(callable(evaluate_symbol))


if __name__ == "__main__":
    unittest.main()
