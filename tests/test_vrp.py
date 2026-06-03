import pytest
from scripts.vrp import compute_vrp


def test_vrp_positive_when_iv_exceeds_rv():
    assert compute_vrp(iv=0.804, rv=0.610) == pytest.approx(0.194, abs=1e-3)


def test_vrp_negative_when_rv_exceeds_iv():
    assert compute_vrp(iv=0.40, rv=0.55) == pytest.approx(-0.15, abs=1e-3)


def test_vrp_label_rich_when_above_threshold():
    assert compute_vrp(iv=0.30, rv=0.10, with_label=True)["label"] == "RICH"


def test_vrp_label_cheap_when_negative():
    assert compute_vrp(iv=0.30, rv=0.40, with_label=True)["label"] == "CHEAP"


def test_vrp_label_neutral_when_small():
    out = compute_vrp(iv=0.30, rv=0.29, with_label=True)
    assert out["label"] == "NEUTRAL"


def test_vrp_raises_on_invalid_input():
    with pytest.raises(ValueError):
        compute_vrp(iv=-0.1, rv=0.2)
    with pytest.raises(ValueError):
        compute_vrp(iv=0.3, rv=float("nan"))
