"""Read the Databricks AI Index page: the weekly share charts embedded in its Next.js (React Server Components)
payload. Shared by fetch.py (which refuses a page that does not parse) and stage.py.

The page publishes no CSV or API. Each chart's props are in the `self.__next_f.push([1, "..."])` script chunks:
concatenated, they form "flight" rows `<id>:<json>`; a chart is the object holding `canvasId` and `layers`
(`[{label, group, values}]`, one value per week). A later chart may give its `weeks` (or `legend`) as a
reference string `$<row id>:<path>` into an earlier row instead of repeating it; React elements on that path
are `["$", type, key, props]`, and the path steps through `props` by name. Week labels carry no year
("Jul 20"): the chart's "Updated <Mon D, YYYY>" line dates the last week, and the weeks before it must be
exactly 7 days apart, each label matching its date. Weeks are taken to start on that Monday (every label
seen on 2026-11-18 is a Monday; the page says "the week of Nov 2").
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# canvasId -> (metric, segment). Shares within a segment sum to 100 per week; `split` is the segment mix itself.
CHARTS = {
    "tokenShareChart": ("tokens", "proprietary"),
    "walletShareChart": ("spend", "proprietary"),
    "ossTokenShareChart": ("tokens", "open_weight"),
    "ossWalletShareChart": ("spend", "open_weight"),
    "openWeightShareChart": ("tokens", "split"),
}
SPLIT_LABELS = {"Proprietary": "proprietary", "Open-weight": "open_weight"}
SUM_TOLERANCE = 1.0  # values are published to 0.1 and up to ~15 layers are stacked (seen: ±0.2)
_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_ROW = re.compile(r"^([0-9a-z]+):(.*)$")
_UPDATED = re.compile(r'"children":"([^"]{3,200})"\}\],\["\$","p",null,\{[^{}]*"children":\["Updated ","([^"]+)"\]')


@dataclass(frozen=True)
class Chart:
    canvas_id: str
    title: str | None
    updated: date
    weeks: list[date]  # week start (Monday)
    layers: list[dict]  # {label, group, values}


def flight_text(html: str) -> str:
    chunks = _CHUNK.findall(html)
    if not chunks:
        raise ValueError("databricks: no Next.js data chunks in the page (layout changed?)")
    return "".join(json.loads(f'"{c}"') for c in chunks)


def _rows(text: str) -> dict[str, object]:
    rows = {}
    for line in text.split("\n"):
        m = _ROW.match(line)
        if not m:
            continue
        try:
            rows[m.group(1)] = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue  # non-JSON rows (module and hint rows) are not needed
    return rows


def _resolve(ref: str, rows: dict) -> object:
    rid, *path = ref[1:].split(":")
    node = rows[rid]
    for step in path:
        if isinstance(node, list) and len(node) == 4 and node[0] == "$" and step == "props":
            node = node[3]
        elif isinstance(node, list):
            node = node[int(step)]
        else:
            node = node[step]
    return node


def _find_charts(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        if "canvasId" in node and "layers" in node:
            out.append(node)
        for v in node.values():
            _find_charts(v, out)
    elif isinstance(node, list):
        for v in node:
            _find_charts(v, out)


def _week_dates(labels: list[str], updated: date, where: str) -> list[date]:
    weeks = [updated - timedelta(days=7 * (len(labels) - 1 - i)) for i in range(len(labels))]
    for label, d in zip(labels, weeks, strict=True):
        if label != f"{d:%b} {d.day}":
            raise ValueError(f"{where}: week label {label!r} does not match {d} (weeks must be 7 days apart)")
    if weeks[0].weekday() != 0:
        raise ValueError(f"{where}: weeks start on {weeks[0]:%A}, not Monday; check the week convention")
    return weeks


def charts(html: str) -> dict[str, Chart]:
    """Every chart in CHARTS, validated: known layout, dated weeks, finite shares in 0–100 that sum to 100."""
    text = flight_text(html)
    rows = _rows(text)
    found: list[dict] = []
    for r in rows.values():
        _find_charts(r, found)
    titles = {m.start(): (m.group(1), m.group(2)) for m in _UPDATED.finditer(text)}
    out: dict[str, Chart] = {}
    for c in found:
        cid = c["canvasId"]
        if cid not in CHARTS:
            continue
        where = f"databricks {cid}"
        if cid in out:
            raise ValueError(f"{where}: appears twice")
        labels = _resolve(c["weeks"], rows) if isinstance(c["weeks"], str) else c["weeks"]
        if not isinstance(labels, list) or not labels or not all(isinstance(s, str) for s in labels):
            raise ValueError(f"{where}: no week labels")
        # the chart's "Updated" line: the nearest one before the chart's props in the payload
        pos = text.find(f'"canvasId":"{cid}"')
        before = [k for k in titles if k < pos]
        if not before:
            raise ValueError(f"{where}: no 'Updated' date")
        title, stamp = titles[max(before)]
        try:
            updated = datetime.strptime(stamp, "%b %d, %Y").date()
        except ValueError:
            raise ValueError(f"{where}: unreadable 'Updated' date {stamp!r}") from None
        weeks = _week_dates(labels, updated, where)
        layers = c["layers"]
        if not isinstance(layers, list) or not layers:
            raise ValueError(f"{where}: no layers")
        for layer in layers:
            vals = layer.get("values") if isinstance(layer, dict) else None
            if not isinstance(layer.get("label"), str) or not isinstance(layer.get("group"), str):
                raise ValueError(f"{where}: a layer has no label or group")
            if not isinstance(vals, list) or len(vals) != len(weeks):
                raise ValueError(
                    f"{where}: layer {layer.get('label')!r} has {len(vals or [])} values, not {len(weeks)}"
                )
            for v in vals:
                if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v) or not 0 <= v <= 100:
                    raise ValueError(f"{where}: layer {layer['label']!r} has a share {v!r} outside 0–100")
        for i, wk in enumerate(weeks):
            total = sum(layer["values"][i] for layer in layers)
            if abs(total - 100) > SUM_TOLERANCE:
                raise ValueError(f"{where}: shares sum to {total:.1f} in the week of {wk}")
        if cid == "openWeightShareChart" and {layer["label"] for layer in layers} != set(SPLIT_LABELS):
            raise ValueError(f"{where}: segments are {[layer['label'] for layer in layers]}, not {list(SPLIT_LABELS)}")
        out[cid] = Chart(
            cid, title, updated, weeks, [{k: layer[k] for k in ("label", "group", "values")} for layer in layers]
        )
    missing = sorted(set(CHARTS) - set(out))
    if missing:
        raise ValueError(f"databricks: charts missing from the page: {missing} (layout changed?)")
    return out


def records(html: str) -> list[dict]:
    """Long rows: one per chart × layer × week."""
    rows = []
    for cid, c in charts(html).items():
        metric, segment = CHARTS[cid]
        for layer in c.layers:
            for wk, v in zip(c.weeks, layer["values"], strict=True):
                rows.append(
                    {
                        "week_start": wk,
                        "chart": cid,
                        "metric": metric,
                        "segment": segment,
                        "provider_group": layer["group"],
                        "label": layer["label"],
                        "share_pct": float(v),
                        "updated": c.updated,
                    }
                )
    return rows
