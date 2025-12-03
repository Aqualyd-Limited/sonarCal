import pytest

def test_import_sonarcal():
    """Check that importing the sonarcal files works."""
    from sonarcal import calculate_gains  # noqa: F401
    from sonarcal import calibration_data  # noqa: F401
    from sonarcal import calibration_gui  # noqa: F401
    from sonarcal import controller  # noqa: F401
    from sonarcal import dialog_config  # noqa: F401
    from sonarcal import dialog_results  # noqa: F401
    from sonarcal import echogram_plotter  # noqa: F401
    from sonarcal import file_ops  # noqa: F401
    from sonarcal import gui_utils  # noqa: F401
    from sonarcal import utils  # noqa: F401

def test_calibration_data(tmp_path):
    """Accumulate, delete, and save calibration results."""

    import os
    from sonarcal import calibration_data
    from datetime import datetime
    
    c = calibration_data.calibrationData()
    
    c.update('34', datetime.now().isoformat(), 16.0, 0.2, -42.4, 0.2, 25.4, 16)
    c.update('64', datetime.now().isoformat(), 16.0, 0.4, -42.4, 0.3, 23.4, 26)
    c.update('S123', datetime.now().isoformat(), 16.0, 0.8, -42.4, 0.25, 20.4, 56)
    c.update('4', datetime.now().isoformat(), 16.0, 0.34, -42.4, 0.55, 29.4, 12)
    assert len(c.df()) == 4
    
    c.remove('4')
    assert len(c.df() == 3)

    save_file = tmp_path/'test_save_results.csv'    
    if os.path.exists(save_file):
        os.remove(save_file)

    c.save(save_file)
    assert os.path.exists(save_file)
    
def test_calculate_gain():
    """Test calculation of transducer gains."""
    
    from sonarcal import calculate_gains
    
    ts = [('2025-11-14T15:20:57.74092', -42.4, 21.4),
          ('2025-11-14T15:20:57.74092', -43.2, 22.4),
          ('2025-11-14T15:20:57.74092', -44.1, 21.6),
          ('2025-11-14T15:20:57.74092', -40.4, 20.2)]
    
    r = calculate_gains.calculate_calibration(ts, -42.4)
    print(r)
    assert r[0] == pytest.approx(0.0995, abs=1e-3)
    assert r[1] == pytest.approx(-42.3004, abs=1e-4)
    assert r[2] == pytest.approx(1.38466, abs=1e-1)
    assert r[3] == pytest.approx(21.4000, abs=1e-3)
    assert r[4] == 4

def test_absorption():
    """Test calculation of acoustic absorption."""
    
    from sonarcal import utils

    a = utils.acousticAbsorption(12.5, 35.2, 11.2, 38000)

    assert a == pytest.approx(0.00995, abs=1e-5)

    