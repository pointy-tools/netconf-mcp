from __future__ import annotations

from argparse import Namespace

from scripts.tnsr_read_only_smoke import TNSR_CONFIG_PROBES, _config_probes


def test_tnsr_profile_expands_expected_default_probes():
    args = Namespace(profile="tnsr", config_xpath=None)
    assert _config_probes(args) == TNSR_CONFIG_PROBES


def test_custom_probe_is_appended_without_duplicates():
    args = Namespace(
        profile="tnsr",
        config_xpath="/interfaces-config/interface[name='LAN']/enabled",
    )
    probes = _config_probes(args)
    assert probes == TNSR_CONFIG_PROBES


def test_custom_profile_only_uses_explicit_xpath():
    args = Namespace(profile="custom", config_xpath="/interfaces-config/interface/name")
    assert _config_probes(args) == ["/interfaces-config/interface/name"]
