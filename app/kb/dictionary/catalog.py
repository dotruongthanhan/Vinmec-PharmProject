"""Kho tên T50 và danh mục RxNorm chỉ đọc tại chỗ."""

from collections import defaultdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.kb.dictionary.axis import Inputs, Match, MatchMethod, resolve_names
from app.kb.dictionary.split import has_strength, split_salt
from app.kb.dictionary.storage import read_json
from app.kb.names import normalize_key
from app.kb.sources.rxnav import BASE_URL, CacheMissing, RxIngredient, RxNav

CATALOG_PATH = "danh_muc/allconcepts_IN_PIN.json"


class CandidateName(BaseModel, frozen=True):
    rxcui: str | None
    ten: str
    tty: Literal["IN", "PIN", "KB"]
    hoat_chat_id: str | None = None
    ma_atc: tuple[str, ...] = ()

    @property
    def identity(self) -> tuple[str, str]:
        return ("rxnorm", self.rxcui) if self.rxcui else ("kb", self.hoat_chat_id or "")


class Catalog:
    """Tra tên chính xác trong trục, danh mục RxNorm và đệm."""

    def __init__(
        self,
        inputs: Inputs,
        matches: dict[str, Match],
        identities: dict[str, RxIngredient],
        rxnav: RxNav,
    ) -> None:
        self.rxnav = rxnav
        self.legacy = inputs.legacy
        self.baseline = identities.copy()
        self.by_rx: dict[str, set[str]] = defaultdict(set)
        self.by_key: dict[str, set[CandidateName]] = defaultdict(set)
        self.axes: dict[str, CandidateName] = {}
        self.concepts: dict[str, CandidateName] = {}
        self.ins: dict[str, set[CandidateName]] = defaultdict(set)
        self.pins: dict[str, set[str]] = defaultdict(set)
        self.pin_targets: dict[str, tuple[CandidateName | None, list[str], bool]] = {}
        self.reverse_pins: dict[str, dict[str, str]] = defaultdict(dict)
        for hid in sorted(inputs.legacy.keys() | identities.keys()):
            concept = identities.get(hid)
            if concept:
                self.by_rx[concept.rxcui].add(hid)
            entry = CandidateName(
                rxcui=concept.rxcui if concept else None,
                ten=inputs.legacy[hid]["ten_inn"] if hid in inputs.legacy else concept.ten_inn,
                tty="KB",
                hoat_chat_id=hid,
                ma_atc=tuple(concept.ma_atc) if concept else (),
            )
            self.axes[hid] = entry
            self._add(entry)
            if concept:
                self._add(entry.model_copy(update={"ten": concept.ten_inn, "tty": "IN"}))
        path = rxnav.source / CATALOG_PATH
        if path.is_file():
            for row in read_json(path)["minConceptGroup"]["minConcept"]:
                rxcui = row["rxcui"]
                ids = self.by_rx.get(rxcui, set())
                hid = next(iter(ids)) if len(ids) == 1 else None
                entry = CandidateName(
                    rxcui=rxcui,
                    ten=row["name"],
                    tty=row["tty"],
                    hoat_chat_id=hid,
                    ma_atc=self.axes[hid].ma_atc if hid else (),
                )
                self.concepts[rxcui] = entry
                self._add(entry)
                key = normalize_key(entry.ten)
                if entry.tty == "PIN":
                    self.pins[key].add(rxcui)
                else:
                    self.ins[key].add(entry)

        for key, match in matches.items():
            if hid := match.hoat_chat_id:
                for evidence in inputs.names[key]:
                    if (
                        evidence.nguon != "mock"
                        and evidence.loai in {"inn", "viet", "muoi"}
                        and not has_strength(evidence.ten_goc)
                    ):
                        self._alias(hid, key)
                        self._alias(hid, evidence.ten_goc)
        brands: dict[str, set[str | None]] = defaultdict(set)
        for raw, split in inputs.dav:
            if brand := normalize_key(raw["ten_thuoc"] or ""):
                ids = [matches[part.ten_chuan_hoa].hoat_chat_id for part in split.thanh_phan]
                hid = ids[0] if len(ids) == 1 and split.trang_thai == "tach_duoc" else None
                brands[brand].add(hid if not inputs.legacy.get(hid, {}).get("thanh_phan") else None)
        # Giữ biệt dược để chặn xung đột, ngoài kho xếp hạng và đích thêm e.
        self.brand_entries: dict[str, CandidateName] = {}
        for brand, ids in brands.items():
            if len(ids) == 1 and (hid := next(iter(ids))):
                self.brand_entries[brand] = self.axes[hid]
        self._read_reverse_pins()

    def _read_reverse_pins(self) -> None:
        manifest = self.rxnav.source / "manifest.json"
        if not manifest.is_file():
            return
        for row in read_json(manifest).get("tep", []):
            url = row["url"]
            if not url.startswith(BASE_URL + "rxcui/") or not url.endswith("/related.json?tty=PIN"):
                continue
            code = urlsplit(url).path.split("/")[-2]
            entry = self.by_code(code)
            if not entry or entry.tty != "IN":
                continue
            try:
                related, ref = self.rxnav._related(code, "PIN")
            except CacheMissing:
                continue
            for pin in related:
                self.reverse_pins[pin][code] = ref

    def _add(self, entry: CandidateName) -> None:
        if not has_strength(entry.ten) and (key := normalize_key(entry.ten)):
            self.by_key[key].add(entry)

    def _alias(self, hid: str, name: str) -> None:
        self._add(self.axes[hid].model_copy(update={"ten": name}))

    def by_code(self, rxcui: str) -> CandidateName | None:
        if rxcui in self.concepts:
            return self.concepts[rxcui]
        ids = self.by_rx.get(rxcui, set())
        if len(ids) == 1:
            hid = next(iter(ids))
            return self.axes[hid].model_copy(
                update={"ten": self.baseline[hid].ten_inn, "tty": "IN"}
            )
        return None

    def exact_entries(self, key: str) -> set[CandidateName]:
        entries = self.by_key.get(key, set())
        return entries | {self.brand_entries[key]} if key in self.brand_entries else entries

    @staticmethod
    def source_ref(rxcui: str) -> str:
        return f"rxnav:{CATALOG_PATH}#rxcui={rxcui}"

    def _pin_by_name(self, rxcui: str) -> CandidateName | None:
        pin = self.concepts.get(rxcui)
        if not pin or pin.tty != "PIN":
            return None
        key = normalize_key(pin.ten)
        base, salt = split_salt(key)
        entries = self.ins.get(base, set())
        if salt and key.startswith(base + " ") and len(entries) == 1:
            return next(iter(entries))
        return None

    def pin_base(self, rxcui: str) -> tuple[CandidateName | None, list[str], bool]:
        if rxcui not in self.pin_targets:
            base = None
            stripped = False
            refs = [self.source_ref(rxcui)]
            reverse = self.reverse_pins.get(rxcui, {})
            try:
                related, ref = self.rxnav._related(rxcui, "IN")
                refs.append(ref)
            except CacheMissing:
                codes = set(reverse)
            else:
                codes = related.keys() | reverse.keys() if related else set()
            refs.extend(reverse.values())
            if not codes and not reverse:
                base = self._pin_by_name(rxcui)
                if base:
                    refs.append(self.source_ref(base.rxcui))
                    stripped = True
            elif len(codes) == 1:
                code = next(iter(codes))
                entry = self.by_code(code)
                if entry and entry.tty == "IN" and code != rxcui:
                    base = entry
            self.pin_targets[rxcui] = base, refs, stripped
        return self.pin_targets[rxcui]

    def match(
        self,
        entry: CandidateName,
        method: MatchMethod,
        identities: dict[str, RxIngredient],
        refs: tuple[str, ...] = (),
    ) -> Match:
        stripped = False
        if entry.tty == "PIN":
            base, pin_refs, stripped = self.pin_base(entry.rxcui)
            refs = (*refs, *pin_refs)
            if base is None:
                return Match(ly_do="pin_thieu_quan_he_in", nguon_ban_ghi_ids=sorted(set(refs)))
            entry = base
        if entry.rxcui and len(self.by_rx.get(entry.rxcui, ())) > 1:
            return Match(ly_do="rxcui_trung_nhieu_khoa_kb")
        hid = entry.hoat_chat_id
        if entry.rxcui in self.concepts:
            refs = (*refs, self.source_ref(entry.rxcui))
        if hid is None:
            canonical = self.concepts[entry.rxcui]
            hid = normalize_key(canonical.ten).replace(" ", "_")
            current = identities.get(hid)
            if hid in self.legacy or (current and current.rxcui != entry.rxcui):
                return Match(ly_do="xung_dot_khoa_hoat_chat", nguon_ban_ghi_ids=list(refs))
            coincident = self.by_key.get(normalize_key(canonical.ten), set())
            if any(other.tty == "IN" and other.rxcui != entry.rxcui for other in coincident):
                return Match(ly_do="xung_dot_khoa_hoat_chat", nguon_ban_ghi_ids=list(refs))
            identities.setdefault(
                hid,
                RxIngredient(
                    rxcui=entry.rxcui,
                    ten_inn=canonical.ten,
                    ma_atc=list(entry.ma_atc),
                    ten_lop_atc=[],
                    nguon_ban_ghi_ids=[self.source_ref(entry.rxcui)],
                ),
            )
        return Match(
            hoat_chat_id=hid,
            cach_khop=method,
            pin_ve_in="bo_muoi" if stripped else None,
            nguon_ban_ghi_ids=sorted(set(refs)),
        )


def baseline(root: Path) -> tuple[Inputs, dict[str, Match], dict[str, RxIngredient], Catalog]:
    inputs = Inputs(root)
    rxnav = RxNav(root / "kb_sources/rxnav")
    matches, identities = resolve_names(inputs, rxnav)
    return inputs, matches, identities, Catalog(inputs, matches, identities, rxnav)
