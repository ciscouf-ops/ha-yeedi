"""Model table sanity checks."""

from deebot_client import hardware as dc_hardware

from custom_components.yeedi.hardware import YEEDI_MODELS, model_name, register_yeedi_models


def test_models_registered_without_shadowing_native_sheets() -> None:
    register_yeedi_models()
    for class_ in YEEDI_MODELS:
        assert class_ in dc_hardware._DEVICES  # noqa: SLF001
        assert class_ not in dc_hardware._NOT_FOUND  # noqa: SLF001
    # The Floor 3 family ships with deebot-client: we must not override it.
    for class_ in ("t5e5o6", "kd0una", "t6kipw", "u3bsxq", "rwp09o"):
        assert class_ not in YEEDI_MODELS


def test_station_follows_dock_kind() -> None:
    register_yeedi_models()
    for class_, (_name, dock) in YEEDI_MODELS.items():
        caps = dc_hardware._DEVICES[class_].capabilities  # noqa: SLF001
        assert (caps.station is not None) == (dock == "empty")


def test_model_name() -> None:
    assert model_name("04z443") == "yeedi vac max"
    assert model_name("zzzzzz") is None
