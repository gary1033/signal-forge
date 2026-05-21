from __future__ import annotations

from collections import Counter

from signal_forge.phase import SignalDigest

ORB_GROUP_KEYS = (
    "accepted",
    "hold",
    "other",
    "range",
    "retest",
    "session",
    "structure",
    "trend",
    "volume",
)
ORB_BLOCKED_GROUP_KEYS = ("range", "retest", "structure", "trend", "volume")
ORB_REASON_GROUPS = {
    "below_or_high": "range",
    "breakout_bar_reentered_range": "structure",
    "breakout_below_ema": "trend",
    "breakout_below_vwap": "trend",
    "breakout_body_too_small": "structure",
    "breakout_distance_too_small": "range",
    "breakout_ema_reference_unavailable": "structure",
    "breakout_ema_slope_blocked": "trend",
    "breakout_not_armed": "retest",
    "breakout_not_fresh_from_or": "structure",
    "breakout_volume_baseline_unavailable": "volume",
    "breakout_volume_blocked": "volume",
    "breakout_vwap_slope_blocked": "trend",
    "ema_inside_opening_range": "structure",
    "hold_intraday_breakout": "hold",
    "opening_range_building": "session",
    "opening_range_too_narrow": "range",
    "opening_range_too_wide": "range",
    "opening_range_unavailable": "session",
    "orb_retest_vwap_breakout": "accepted",
    "orb_volume_vwap_breakout": "accepted",
    "outside_session": "session",
    "outside_signal_window": "session",
    "retest_not_touched": "retest",
    "session_reset": "session",
    "session_timestamp_required": "session",
    "volume_warmup": "volume",
    "waiting_for_retest_confirmation": "retest",
}


def _build_reason_count_items(reason_counts: Counter[str]) -> list[dict[str, int | str]]:
    """
    用途與流程：把 ORB attribution 內部使用的 reason Counter 轉成 deterministic list[dict] 結構，統一 accepted / blocked / hold 三種 reason 統計的排序與輸出格式。
    參數：reason_counts（Counter[str]）是 reason 到出現次數的計數器；空 Counter 代表這一類 reason 目前沒有樣本。
    回傳與錯誤：回傳 list[dict[str, int | str]]；若 Counter 為空則回傳空清單，不主動丟錯。
    """
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _orb_reason_group_for_digest(digest: SignalDigest) -> str:
    """
    用途與流程：依單筆 SignalDigest 的 entry / hold / flatten 語意與 reason 字串，把 ORB 訊號歸類到 accepted、hold、session、range、structure、trend、volume、retest 或 other。
    參數：digest（SignalDigest）需已完成 deterministic normalize，且包含 target_position、position_change、reason、is_long_entry 與 is_flatten 欄位。
    回傳與錯誤：回傳 str；若 reason 不在目前 ORB 分類表內，回傳 other，不主動丟錯。
    """
    epsilon = 1e-12
    is_hold = abs(digest.target_position) > epsilon and abs(digest.position_change) <= epsilon
    if digest.is_long_entry:
        return "accepted"
    if is_hold:
        return "hold"
    return ORB_REASON_GROUPS.get(digest.reason, "other")


def build_orb_filter_attribution(
    digests: list[SignalDigest],
) -> dict[str, object] | None:
    """
    用途與流程：從單次 backtest 的 SignalDigest 序列推導 ORB filter attribution，整理 accepted、hold、blocked 與各 filter group 的 deterministic 統計，讓 generic reporting 不必直接知道 ORB taxonomy 細節。
    參數：digests（list[SignalDigest]）是單一 run 的完整訊號摘要序列；若 reasons 與 ORB contract 無關，函式會直接返回 None。
    回傳與錯誤：回傳 dict[str, object] | None；若這批 digests 不屬於 ORB 語意，回傳 None，不主動丟錯。
    """
    if not digests:
        return None

    known_orb_reasons = set(ORB_REASON_GROUPS.keys())
    reasons = {digest.reason for digest in digests if digest.reason}
    if not any(reason in known_orb_reasons or reason.startswith("orb_") for reason in reasons):
        return None

    group_counts: Counter[str] = Counter()
    blocked_reason_counts: Counter[str] = Counter()
    accepted_reason_counts: Counter[str] = Counter()
    hold_reason_counts: Counter[str] = Counter()
    epsilon = 1e-12

    for digest in digests:
        group = _orb_reason_group_for_digest(digest)
        group_counts[group] += 1

        is_hold = abs(digest.target_position) > epsilon and abs(digest.position_change) <= epsilon
        if digest.is_long_entry:
            accepted_reason_counts[digest.reason] += 1
            continue
        if is_hold:
            hold_reason_counts[digest.reason] += 1
            continue
        if not digest.is_flatten and group in ORB_BLOCKED_GROUP_KEYS:
            blocked_reason_counts[digest.reason] += 1

    deterministic_group_counts = {
        key: int(group_counts.get(key, 0)) for key in ORB_GROUP_KEYS
    }
    return {
        "accepted_entry_count": sum(accepted_reason_counts.values()),
        "blocked_signal_count": sum(blocked_reason_counts.values()),
        "hold_count": sum(hold_reason_counts.values()),
        "group_counts": deterministic_group_counts,
        "accepted_reason_counts": _build_reason_count_items(accepted_reason_counts),
        "blocked_reason_counts": _build_reason_count_items(blocked_reason_counts),
        "hold_reason_counts": _build_reason_count_items(hold_reason_counts),
    }


def validate_orb_filter_attribution_dict(
    *,
    orb_filter_attribution: dict[str, object],
    bar_count: int,
    flatten_count: int,
    hold_count: int,
    long_entry_count: int,
) -> None:
    """
    用途與流程：驗證 ORB filter attribution 區塊的 deterministic schema 與統計關係，讓 ORB 專屬 validator 規則留在專用模組，不再散落在 generic reporting 檔案中。
    參數：orb_filter_attribution 是 trace summary 內的 ORB attribution dict；bar_count、flatten_count、hold_count、long_entry_count 來自同一份 trace summary 主體統計。
    回傳與錯誤：回傳 None；若 attribution 欄位缺失、型別錯誤或統計關係不一致，拋出 ValueError。
    """
    del flatten_count
    required_keys = {
        "accepted_entry_count",
        "accepted_reason_counts",
        "blocked_reason_counts",
        "blocked_signal_count",
        "group_counts",
        "hold_count",
        "hold_reason_counts",
    }
    if set(orb_filter_attribution.keys()) != required_keys:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution must have deterministic keys"
        )

    accepted_entry_count = orb_filter_attribution.get("accepted_entry_count")
    blocked_signal_count = orb_filter_attribution.get("blocked_signal_count")
    attributed_hold_count = orb_filter_attribution.get("hold_count")
    group_counts = orb_filter_attribution.get("group_counts")
    accepted_reason_counts = orb_filter_attribution.get("accepted_reason_counts")
    blocked_reason_counts = orb_filter_attribution.get("blocked_reason_counts")
    hold_reason_counts = orb_filter_attribution.get("hold_reason_counts")

    for label, value in (
        ("accepted_entry_count", accepted_entry_count),
        ("blocked_signal_count", blocked_signal_count),
        ("hold_count", attributed_hold_count),
    ):
        if not isinstance(value, int) or value < 0 or value > bar_count:
            raise ValueError(
                f"trace summary trace_summary.orb_filter_attribution.{label} must be a non-negative int <= bar_count"
            )

    if not isinstance(group_counts, dict):
        raise ValueError("trace summary trace_summary.orb_filter_attribution.group_counts must be a dict")
    if set(group_counts.keys()) != set(ORB_GROUP_KEYS):
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.group_counts must have deterministic keys"
        )
    if sum(value for value in group_counts.values() if isinstance(value, int)) != bar_count or any(
        (not isinstance(value, int)) or value < 0 or value > bar_count
        for value in group_counts.values()
    ):
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.group_counts must be non-negative ints summing to bar_count"
        )

    def parse_reason_items(value: object, *, label: str) -> list[tuple[str, int]]:
        """
        用途與流程：把 attribution 內的 reason-count list 驗證並轉成 tuple 清單，讓 accepted / blocked / hold 三種列表重用同一套排序與加總檢查。
        參數：value 是待驗證欄位；label 是錯誤訊息用的欄位名稱。
        回傳與錯誤：回傳 list[tuple[str, int]]；若格式不是 deterministic reason-count list，拋出 ValueError。
        """
        if not isinstance(value, list):
            raise ValueError(f"trace summary trace_summary.orb_filter_attribution.{label} must be a list")
        parsed_items: list[tuple[str, int]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict) or set(item.keys()) != {"reason", "count"}:
                raise ValueError(
                    f"trace summary trace_summary.orb_filter_attribution.{label}[{index}] must have keys ['reason', 'count']"
                )
            reason = item.get("reason")
            count = item.get("count")
            if not isinstance(reason, str) or not reason:
                raise ValueError(
                    f"trace summary trace_summary.orb_filter_attribution.{label}[{index}].reason must be a non-empty str"
                )
            if not isinstance(count, int) or count <= 0:
                raise ValueError(
                    f"trace summary trace_summary.orb_filter_attribution.{label}[{index}].count must be a positive int"
                )
            parsed_items.append((reason, count))
        if parsed_items != sorted(parsed_items, key=lambda item: (-item[1], item[0])):
            raise ValueError(
                f"trace summary trace_summary.orb_filter_attribution.{label} must be sorted by (-count, reason)"
            )
        if len({reason for reason, _count in parsed_items}) != len(parsed_items):
            raise ValueError(
                f"trace summary trace_summary.orb_filter_attribution.{label} reasons must be unique"
            )
        return parsed_items

    parsed_accepted = parse_reason_items(accepted_reason_counts, label="accepted_reason_counts")
    parsed_blocked = parse_reason_items(blocked_reason_counts, label="blocked_reason_counts")
    parsed_hold = parse_reason_items(hold_reason_counts, label="hold_reason_counts")

    if sum(count for _reason, count in parsed_accepted) != accepted_entry_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.accepted_reason_counts total must match accepted_entry_count"
        )
    if sum(count for _reason, count in parsed_blocked) != blocked_signal_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.blocked_reason_counts total must match blocked_signal_count"
        )
    if sum(count for _reason, count in parsed_hold) != attributed_hold_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.hold_reason_counts total must match hold_count"
        )
    if accepted_entry_count != long_entry_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.accepted_entry_count must match long_entry_count"
        )
    if attributed_hold_count != hold_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.hold_count must match hold_count"
        )
    if int(group_counts["accepted"]) != accepted_entry_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.group_counts.accepted must match accepted_entry_count"
        )
    if int(group_counts["hold"]) != hold_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.group_counts.hold must match hold_count"
        )

    expected_blocked_signal_count = sum(int(group_counts[key]) for key in ORB_BLOCKED_GROUP_KEYS)
    if blocked_signal_count != expected_blocked_signal_count:
        raise ValueError(
            "trace summary trace_summary.orb_filter_attribution.blocked_signal_count must match blocked filter group totals"
        )
