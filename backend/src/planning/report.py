"""Machine-readable planning report and its JSON / Markdown / CSV exports.

``build_report`` turns a result dict into a section/block structure
(``Report``); the exporters render that structure or the underlying result.
Nothing is recomputed here -- every number is copied from the result.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

SECTION_IDS = (
    "executive-summary",
    "scenario",
    "alternatives",
    "methodology",
    "performance",
    "safety",
    "environmental",
    "reliability",
    "findings",
    "limitations",
    "reproducibility",
)


class TextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text"] = "text"
    text: str


class ListBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["list"] = "list"
    items: List[str]


class TableBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["table"] = "table"
    caption: str = ""
    columns: List[str]
    rows: List[List[Union[str, float, int, None]]]


Block = Union[TextBlock, ListBlock, TableBlock]


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    blocks: List[Block] = Field(default_factory=list)


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    scenarioFingerprint: str
    sections: List[Section]
    exports: List[str] = Field(default_factory=lambda: ["json", "md", "csv"])


def _g(group: Dict[str, Any], key: str, field: str = "mean") -> Any:
    return ((group.get("values") or {}).get(key) or {}).get(field)


def _ci(group: Dict[str, Any], key: str) -> str:
    v = (group.get("values") or {}).get(key) or {}
    if v.get("ciLow") is None:
        return "n/a"
    return f"{v['ciLow']:g} to {v['ciHigh']:g}"


def _metric_table(result: Dict[str, Any], group: str, caption: str) -> TableBlock:
    labels = {a["id"]: a["label"] for a in result["alternatives"]}
    keys: List[str] = []
    for r in result["results"]:
        for k in (r.get(group) or {}).get("values", {}):
            if k not in keys:
                keys.append(k)
    rows: List[List[Any]] = []
    for r in result["results"]:
        g = r.get(group) or {}
        for k in keys:
            if k in (g.get("values") or {}):
                v = g["values"][k]
                rows.append(
                    [
                        labels[r["alternativeId"]],
                        r["demandScale"],
                        v["label"],
                        v["mean"],
                        v["std"],
                        _ci(g, k),
                        v["n"],
                    ]
                )
    return TableBlock(
        caption=caption,
        columns=["Alternative", "Demand scale", "Indicator", "Mean", "Std", "CI", "n"],
        rows=rows,
    )


def build_report(result: Dict[str, Any]) -> Dict[str, Any]:
    sc = result["scenario"]
    labels = {a["id"]: a["label"] for a in result["alternatives"]}
    summary = result["summary"]
    meta = result["meta"]

    def section(sid: str, title: str, *blocks: Block) -> Section:
        return Section(id=sid, title=title, blocks=list(blocks))

    findings = result["findings"]
    sections = [
        section(
            "executive-summary",
            "Executive summary",
            TextBlock(
                text=(
                    f"{len(result['alternatives'])} alternative(s) were compared for "
                    f"scenario '{sc['name']}' (fingerprint {sc['fingerprint']}) at demand "
                    f"scale(s) {', '.join(f'x{s:g}' for s in summary['scales'])} over "
                    f"{summary['seeds']} repetition(s). {len(findings)} finding(s) follow. "
                    "This report presents evidence for this scenario only and does not "
                    "name a universally better option."
                )
            ),
            ListBlock(
                items=[f["statement"] for f in findings if f["kind"] != "note"][:8]
            ),
        ),
        section(
            "scenario",
            "Scenario",
            TableBlock(
                caption="Arms",
                columns=["Arm", "Lanes", "Length (m)", "Vehicles/h", "Turning"],
                rows=[
                    [
                        d,
                        a["lanes"],
                        a["length"],
                        a["vehiclesPerHour"],
                        json.dumps(a["turning"], sort_keys=True),
                    ]
                    for d, a in sc["geometry"]["arms"].items()
                ],
            ),
            TextBlock(
                text=f"Vehicle mix: {json.dumps(sc['vehicleMix'], sort_keys=True)}"
                + (
                    " (default passenger-car population)"
                    if sc.get("vehicleMixDefaulted")
                    else ""
                )
                + f". Duration {sc['simulation']['duration']:g}s, warm-up {sc['simulation']['warmup']:g}s."
            ),
        ),
        section(
            "alternatives",
            "Alternatives",
            TableBlock(
                columns=[
                    "Id",
                    "Label",
                    "Strategy",
                    "Baseline",
                    "Changes from scenario",
                    "Fingerprint",
                ],
                rows=[
                    [
                        a["id"],
                        a["label"],
                        a["strategyTitle"],
                        "yes" if a["isBaseline"] else "no",
                        ", ".join(a["changesFromBase"]) or "none",
                        a["fingerprint"],
                    ]
                    for a in result["alternatives"]
                ],
            ),
        ),
        section(
            "methodology",
            "Methodology",
            TextBlock(
                text=(
                    "Each alternative is simulated under identical seeds, so per-seed "
                    "differences against the baseline are paired. Intervals are two-sided "
                    f"Student-t at {result['reliability']['confidenceLevel']:.0%}. "
                    + str(
                        (result["comparison"].get("method") or {}).get(
                            "delayComparison", ""
                        )
                    )
                )
            ),
        ),
        section(
            "performance",
            "Performance",
            _metric_table(result, "performance", "Performance indicators"),
        ),
    ]
    if any("safety" in r for r in result["results"]):
        sections.append(
            section(
                "safety",
                "Safety indicators (exploratory)",
                _metric_table(result, "safety", "Safety indicators"),
                TextBlock(
                    text=next(
                        r["safety"].get("note", "")
                        for r in result["results"]
                        if "safety" in r
                    )
                ),
            )
        )
    if any("environmental" in r for r in result["results"]):
        env = next(
            r["environmental"] for r in result["results"] if "environmental" in r
        )
        sections.append(
            section(
                "environmental",
                "Environmental indicators (proxies)",
                _metric_table(result, "environmental", "Environmental proxies"),
                TextBlock(text=env.get("note", "")),
                ListBlock(
                    items=[
                        f"{u['label']}: {u['reason']}"
                        for u in env.get("unavailable", [])
                    ]
                ),
            )
        )
    rel = result["reliability"]
    sections.append(
        section(
            "reliability",
            "Reliability",
            TextBlock(
                text=f"{rel['repetitions']} repetition(s), seeds {rel['seeds']}, sample adequacy: {rel['sampleAdequacy']}."
            ),
            ListBlock(
                items=[f["message"] for f in rel["flags"]]
                or ["No reliability warnings."]
            ),
        )
    )
    sections.append(
        section(
            "findings",
            "Findings",
            TableBlock(
                columns=["Id", "Kind", "Statement", "Confidence"],
                rows=[
                    [f["id"], f["kind"], f["statement"], f["confidence"]]
                    for f in findings
                ],
            ),
        )
    )
    sections.append(
        section("limitations", "Limitations", ListBlock(items=result["limitations"]))
    )
    sections.append(
        section(
            "reproducibility",
            "Reproducibility",
            TableBlock(
                columns=["Item", "Value"],
                rows=[
                    ["Git commit", meta["gitCommit"]],
                    ["Python", meta["pythonVersion"]],
                    ["Input fingerprint", meta["inputFingerprint"]],
                    ["Scenario fingerprint", meta["scenarioFingerprint"]],
                    ["Result fingerprint", meta.get("resultFingerprint")],
                    ["Calibration run", meta.get("calibrationRunId") or "not provided"],
                    [
                        "Observations fingerprint",
                        meta.get("calibrationFingerprint") or "not provided",
                    ],
                    ["Network fingerprint", meta.get("networkFingerprint")],
                    ["Seeds", ", ".join(str(s) for s in meta["seeds"])],
                    ["Time step (s)", meta["timeStep"]],
                    ["Engine model", meta["engineModel"]],
                ],
            ),
        )
    )
    _ = labels
    return Report(
        title=f"Planning report: {result['name']}",
        scenarioFingerprint=sc["fingerprint"],
        sections=sections,
    ).model_dump(mode="json")


def to_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def to_markdown(result: Dict[str, Any]) -> str:
    report = result["report"]
    out = [f"# {report['title']}", ""]
    for sec in report["sections"]:
        out += [f"## {sec['title']}", ""]
        for b in sec["blocks"]:
            if b["type"] == "text":
                out += [b["text"], ""]
            elif b["type"] == "list":
                out += [f"- {i}" for i in b["items"]] + [""]
            else:
                if b.get("caption"):
                    out += [f"*{b['caption']}*", ""]
                out.append("| " + " | ".join(b["columns"]) + " |")
                out.append("|" + "---|" * len(b["columns"]))
                for row in b["rows"]:
                    out.append(
                        "| "
                        + " | ".join(
                            "" if c is None else str(c).replace("|", "/") for c in row
                        )
                        + " |"
                    )
                out.append("")
    return "\n".join(out)


CSV_COLUMNS = [
    "scenarioFingerprint",
    "alternativeId",
    "strategy",
    "demandScale",
    "group",
    "indicator",
    "status",
    "unit",
    "mean",
    "std",
    "min",
    "max",
    "ciLow",
    "ciHigh",
    "n",
]


def to_csv(result: Dict[str, Any]) -> str:
    """Long format: one row per alternative x demand scale x indicator.

    Unavailable indicators are rows with status ``unavailable`` and empty
    numbers -- never zeros.
    """
    strategy = {a["id"]: a["strategy"] for a in result["alternatives"]}
    fp = result["scenario"]["fingerprint"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in result["results"]:
        for group in ("performance", "safety", "environmental", "reliability"):
            g = r.get(group)
            if not g:
                continue
            for key, v in g["values"].items():
                w.writerow(
                    [
                        fp,
                        r["alternativeId"],
                        strategy[r["alternativeId"]],
                        r["demandScale"],
                        group,
                        key,
                        g["status"],
                        v["unit"],
                        v["mean"],
                        v["std"],
                        v["min"],
                        v["max"],
                        v["ciLow"],
                        v["ciHigh"],
                        v["n"],
                    ]
                )
            for u in g["unavailable"]:
                w.writerow(
                    [
                        fp,
                        r["alternativeId"],
                        strategy[r["alternativeId"]],
                        r["demandScale"],
                        group,
                        u["key"],
                        "unavailable",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
    return buf.getvalue()


def export(result: Dict[str, Any], fmt: str) -> Dict[str, str]:
    """``{content, mediaType, filename}`` for ``json`` / ``md`` / ``csv``."""
    fmt = fmt.lower()
    stem = f"planning-{result['scenario']['fingerprint']}"
    if fmt == "json":
        return {
            "content": to_json(result),
            "mediaType": "application/json",
            "filename": f"{stem}.json",
        }
    if fmt in ("md", "markdown"):
        return {
            "content": to_markdown(result),
            "mediaType": "text/markdown",
            "filename": f"{stem}.md",
        }
    if fmt == "csv":
        return {
            "content": to_csv(result),
            "mediaType": "text/csv",
            "filename": f"{stem}.csv",
        }
    raise ValueError(f"Unsupported export format {fmt!r}; use json, md or csv")
