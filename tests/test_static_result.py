"""The §7 table derives verdicts from the same row-attributed findings."""

import json

from conftest import ad_data, config_data, make_apk_facts, make_placement, make_spec

from apkverify.checks.static_result import build
from apkverify.model import RcValue, Severity


def test_clean_result_and_states() -> None:
    values = (
        RcValue("admob_id", json.dumps(ad_data()), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(config_data()), "config_show_ads.json"),
    )
    result = build(make_spec(), values, make_apk_facts())
    assert result.passed and result.findings == ()
    status = result.statuses[0]
    assert (status.rc_id, status.rc_config, status.code_space, status.code_config, status.verdict) == (
        "OK",
        "BẬT",
        "OK",
        "OK",
        "ĐẠT",
    )


def test_verdict_rows_sorting_and_global_findings() -> None:
    placements = (
        make_placement(row=9),
        make_placement(row=7, config_name="off"),
        make_placement(row=8, space_name="missing"),
        make_placement(row=6, network_name="typo"),
    )
    config = config_data(
        listConfig=[
            dict(configName="home_bottom", isOn=True, type="native"),
            dict(configName="off", isOn=False, type="native"),
        ]
    )
    remote = (
        RcValue("admob_id", json.dumps(ad_data()), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(config), "config_show_ads.json"),
    )
    apk = make_apk_facts(admob_app_id=None, dex_strings=make_apk_facts().dex_strings | {"off"})
    result = build(make_spec(*placements), remote, apk)
    assert [s.placement.row for s in result.statuses] == [9, 7, 8, 6]
    assert [s.verdict for s in result.statuses] == ["CẢNH BÁO", "CẢNH BÁO", "LỖI", "CẢNH BÁO"]
    assert not result.passed
    assert result.count(Severity.ERROR) == 4
    order = [(-f.severity, f.code, f.rows[0] if f.rows else 0, f.message) for f in result.findings]
    assert order == sorted(order)
    assert result.rc_values == remote


def test_global_error_does_not_mark_unrelated_row() -> None:
    remote = (
        RcValue("admob_id", json.dumps(ad_data()), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(config_data()), "config_show_ads.json"),
    )
    result = build(make_spec(make_placement(network_name="different")), remote, make_apk_facts(admob_app_id=None))
    assert not result.passed
    assert result.statuses[0].verdict == "ĐẠT"
