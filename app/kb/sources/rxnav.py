"""Tra RxNorm và RxClass với bộ đệm phản hồi thô."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from pydantic import BaseModel

from app.kb.dictionary.http import SourceHTTP
from app.kb.dictionary.storage import Row, store, write_json
from app.kb.fetch.client import FetchError, MalformedResponseError

BASE_URL = "https://rxnav.nlm.nih.gov/REST/"
_ATC = re.compile(r"[A-Z](?:\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?)?")


class RxIngredient(BaseModel):
    rxcui: str
    ten_inn: str
    ma_atc: list[str]
    ten_lop_atc: list[str]
    nguon_ban_ghi_ids: list[str]


class CacheMissing(FetchError):
    """Chưa có phản hồi nguồn cho truy vấn cần tra."""


class RxNav:
    def __init__(self, source: Path, http: SourceHTTP | None = None, *, refresh: bool = False):
        self.source = source
        self.http = http
        self.refresh = refresh
        self.files: dict[str, Row] = {}
        self.reused = 0
        self.downloaded = 0
        self.started = datetime.now(UTC).isoformat()
        self._responses: dict[str, tuple[Row, str]] = {}

    def _get(self, endpoint: str, **params: str) -> tuple[Row, str]:
        url = BASE_URL + endpoint
        query = url + "?" + urlencode(sorted(params.items()))
        if query in self._responses:
            return self._responses[query]
        key = hashlib.sha256(query.encode()).hexdigest()
        relative = f"cache/{key}.json"
        path = self.source / relative
        from_cache = path.exists() and not self.refresh
        if from_cache:
            raw = path.read_bytes()
        else:
            if self.http is None:
                raise CacheMissing("thieu_dem_rxnav")
            response = self.http.request("GET", url, params=params)
            if response.status_code != 200:
                raise FetchError(f"RxNav trả HTTP {response.status_code} tại {endpoint}")
            raw = response.content
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise TypeError
        except (ValueError, TypeError) as exc:
            raise MalformedResponseError("RxNav không trả đối tượng JSON") from exc
        if from_cache:
            self.reused += 1
        else:
            store(path, raw)
            self.downloaded += 1
        self.files[key] = {
            "duong_dan": relative,
            "url": query,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        result = payload, f"rxnav:{key}"
        self._responses[query] = result
        return result

    def _atc(self, rxcui: str) -> tuple[dict[str, str], dict[str, str], str]:
        body, ref = self._get("rxclass/class/byRxcui.json", rxcui=rxcui, relaSource="ATC")
        rows = (body.get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo") or []
        types: dict[str, str] = {}
        classes: dict[str, str] = {}
        for row in rows:
            concept = row.get("minConcept") or {}
            if concept.get("rxcui") != rxcui:
                continue
            tty, name = concept.get("tty"), concept.get("name")
            if isinstance(tty, str) and isinstance(name, str) and name.strip():
                types.setdefault(tty, name)
            clazz = row.get("rxclassMinConceptItem") or {}
            code, name = clazz.get("classId"), clazz.get("className")
            if (
                row.get("relaSource", "ATC") == "ATC"
                and isinstance(code, str)
                and _ATC.fullmatch(code)
                and isinstance(name, str)
                and name.strip()
            ):
                classes.setdefault(code, name)
        return types, classes, ref

    def _related(self, rxcui: str, tty: str) -> tuple[dict[str, str], str]:
        body, ref = self._get(f"rxcui/{rxcui}/related.json", tty=tty)
        groups = (body.get("relatedGroup") or {}).get("conceptGroup") or []
        concepts = {}
        for group in groups:
            if group.get("tty") == tty:
                for item in group.get("conceptProperties") or []:
                    if item.get("rxcui") and item.get("name"):
                        concepts[item["rxcui"]] = item["name"]
        return concepts, ref

    def _ingredient(self, rxcui: str) -> tuple[tuple[str, str] | None, set[str], str]:
        types, _, ref = self._atc(rxcui)
        refs = {ref}
        if set(types) == {"IN"}:
            return (rxcui, types["IN"]), refs, ""
        if types and set(types) != {"PIN"}:
            return None, refs, "rxnav_khong_co_in_pin"
        related, ref = self._related(rxcui, "IN")
        refs.add(ref)
        if rxcui in related and not types:
            return (rxcui, related[rxcui]), refs, ""
        if len(related) == 1 and rxcui not in related:
            base, name = next(iter(related.items()))
            if "PIN" in types:
                return (base, name), refs, ""
            pins, ref = self._related(base, "PIN")
            refs.add(ref)
            if rxcui in pins:
                return (base, name), refs, ""
        elif not related and not types:
            pins, ref = self._related(rxcui, "PIN")
            refs.add(ref)
            for pin in sorted(pins):
                bases, ref = self._related(pin, "IN")
                refs.add(ref)
                if rxcui in bases:
                    return (rxcui, bases[rxcui]), refs, ""
        reason = "pin_khong_co_mot_in" if "PIN" in types else "rxnav_khong_co_in_pin"
        return None, refs, reason

    def exact(self, name: str) -> tuple[RxIngredient | None, str]:
        """Chỉ nhận IN hoặc PIN phân giải về đúng một IN."""
        body, search_ref = self._get("rxcui.json", name=name, search="0", allsrc="0")
        if "idGroup" not in body:
            raise MalformedResponseError("RxNav thiếu idGroup")
        ids = (body["idGroup"] or {}).get("rxnormId") or []
        candidates: dict[str, tuple[str, set[str]]] = {}
        for rxcui in ids:
            if not isinstance(rxcui, str) or not rxcui.isascii() or not rxcui.isdecimal():
                raise MalformedResponseError("Mã RxCUI không hợp lệ")
            ingredient, refs, error = self._ingredient(rxcui)
            if error == "pin_khong_co_mot_in":
                return None, error
            if ingredient is None:
                continue
            rxcui, inn = ingredient
            if rxcui not in candidates:
                candidates[rxcui] = inn, refs
            else:
                candidates[rxcui][1].update(refs)
        if len(candidates) != 1:
            return None, "rxnav_nhieu_in" if candidates else "rxnav_khong_co_in_pin"
        rxcui, (name, refs) = next(iter(candidates.items()))
        _, classes, atc_ref = self._atc(rxcui)
        codes = sorted(classes)
        return RxIngredient(
            rxcui=rxcui,
            ten_inn=name,
            ma_atc=codes,
            ten_lop_atc=[classes[code] for code in codes],
            nguon_ban_ghi_ids=sorted(refs | {atc_ref, search_ref}),
        ), ""

    def suggestions(self, name: str) -> tuple[list[Row], str]:
        body, ref = self._get("approximateTerm.json", term=name, maxEntries="5", option="1")
        candidates = (body.get("approximateGroup") or {}).get("candidate") or []
        suggestions = []
        seen = set()
        for candidate in candidates:
            rxcui = candidate.get("rxcui")
            if (
                rxcui in seen
                or not isinstance(rxcui, str)
                or not rxcui.isascii()
                or not rxcui.isdecimal()
            ):
                continue
            seen.add(rxcui)
            name = candidate.get("name")
            refs = [ref]
            if not name:
                types, _, class_ref = self._atc(rxcui)
                if len(types) == 1:
                    name = next(iter(types.values()))
                    refs.append(class_ref)
            suggestions.append(
                {
                    "rxcui": rxcui,
                    "ten_rxnav": name,
                    "diem": candidate.get("score"),
                    "nguon_ban_ghi_ids": refs,
                }
            )
        return suggestions, ref

    def manifest(self, status: str, counts: Row, *, error: str | None = None) -> None:
        write_json(
            self.source / "manifest.json",
            {
                "ngay_lay": self.started,
                "url": BASE_URL,
                "trang_thai": status,
                "so_phan_hoi_moi": self.downloaded,
                "so_phan_hoi_doc_dem": self.reused,
                **counts,
                "loi": error,
                "tep": list(self.files.values()),
            },
        )
