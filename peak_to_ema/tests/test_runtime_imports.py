def test_runtime_entrypoint_imports() -> None:
    from src import main
    from src.core.signal_engine import evaluate_symbol

    assert callable(main.main)
    assert callable(evaluate_symbol)
