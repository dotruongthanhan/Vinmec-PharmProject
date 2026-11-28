"""Dựng tập tên tra và chọn đối chiếu có nguồn neo."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.kb.dictionary.split import SplitResult, split_components, split_salt
from app.kb.dictionary.storage import Row, read_json, read_jsonl
from app.kb.names import normalize_key
from app.kb.sources.rxnav import CacheMissing, RxIngredient, RxNav

VIET_TO_INTERNATIONAL = {
    "aciclovir": "acyclovir",
    "acid clavulanic": "clavulanic acid",
    "acid valproic": "valproic acid",
    "amoxicilin": "amoxicillin",
    "cefoperazon": "cefoperazone",
    "ceftriaxon": "ceftriaxone",
    "colistimethat": "colistimethate",
    "colistimethat natri": "colistimethate sodium",
    "kali clorid": "potassium chloride",
    "natri clorid": "sodium chloride",
    "paracetamol": "acetaminophen",
    "piperacilin": "piperacillin",
    "sulfamethoxazol": "sulfamethoxazole",
    "acetylcystein": "acetylcysteine",
    "acid ascorbic": "ascorbic acid",
    "acid folic": "folic acid",
    "acid ursodeoxycholic": "ursodeoxycholic acid",
    "alverin": "alverine",
    "betamethason": "betamethasone",
    "bromhexin": "bromhexine",
    "cafein": "caffeine",
    "carbocistein": "carbocisteine",
    "cefpodoxim": "cefpodoxime",
    "chlorpheniramin": "chlorpheniramine",
    "citicolin": "citicoline",
    "clorpheniramin": "chlorpheniramine",
    "cloramphenicol": "chloramphenicol",
    "desloratadin": "desloratadine",
    "dextromethorphan hydrobromid": "dextromethorphan hydrobromide",
    "domperidon": "domperidone",
    "fenofibrat": "fenofibrate",
    "fexofenadin": "fexofenadine",
    "glimepirid": "glimepiride",
    "glucosamin": "glucosamine",
    "hydroclorothiazid": "hydrochlorothiazide",
    "loratadin": "loratadine",
    "magnesi hydroxyd": "magnesium hydroxide",
    "natri bicarbonat": "sodium bicarbonate",
    "nicotinamid": "niacinamide",
    "phenylephrin": "phenylephrine",
    "prednisolon": "prednisolone",
    "prednison": "prednisone",
    "pseudoephedrin": "pseudoephedrine",
    "pyridoxin": "pyridoxine",
    "rabeprazol": "rabeprazole",
    "simethicon": "simethicone",
    "thiamin mononitrat": "thiamine mononitrate",
}


class Evidence(BaseModel):
    nguon: Literal["dav", "kb", "mock"]
    ma_ban_ghi_nguon: str
    ten_goc: str
    loai: Literal["inn", "viet", "muoi", "biet_duoc"]

    @property
    def reference(self) -> str:
        return f"{self.nguon}:{self.ma_ban_ghi_nguon}"


MatchMethod = Literal[
    "ma_chuan",
    "bang_viet_quoc_te",
    "rxnav_chinh_xac",
    "them_e_cuoi",
    "bang_vitamin",
    "nguoi_duyet",
    "ngu_nghia_tu_nhan",
]


class Match(BaseModel):
    hoat_chat_id: str | None = None
    cach_khop: MatchMethod | None = None
    pin_ve_in: Literal["bo_muoi"] | None = None
    ly_do: str | None = None
    goi_y: list[Row] = []
    nguon_ban_ghi_ids: list[str] = []
    khoa_nguon: str | None = None


class Inputs:
    """Tập tên chỉ gồm danh mục hoạt chất và thành phần có tên."""

    def __init__(self, root: Path):
        legacy = read_json(root / "kb/hoat_chat.json")
        self.legacy = {row["hoat_chat_id"]: row for row in legacy["hoat_chat"]}
        self.labels: dict[str, list[str]] = legacy["nhan"]
        self.names: dict[str, list[Evidence]] = defaultdict(list)
        self.mock_groups: dict[str, set[str]] = defaultdict(set)
        self.legacy_keys: dict[str, set[str]] = defaultdict(set)
        self.dav: list[tuple[Row, SplitResult]] = []
        self.dav_manifest: Row = {}
        self._read_legacy()
        self._read_mock(root / "mock")
        stage = root / "kb_staging/tu_dien/dav_thuoc.jsonl"
        manifest = root / "kb_sources/dav/manifest.json"
        if manifest.exists():
            self.dav_manifest = read_json(manifest)
        if self.dav_manifest.get("trang_thai") == "xong":
            self._read_dav(stage)
        elif stage.exists():
            raise ValueError("Tầng 1 DAV có sẵn nhưng manifest chưa xác nhận lượt tải đầy đủ")

    def _read_legacy(self) -> None:
        for hid, row in self.legacy.items():
            ref = f"hoat_chat:{hid}"
            raw_names = [(hid, "inn"), (row["ten_inn"], "inn"), (row["ten_viet"], "viet")]
            for value in row.get("dong_nghia") or []:
                kind = "muoi" if split_salt(value)[1] else "viet"
                raw_names.append((value, kind))
            for value, kind in raw_names:
                key = normalize_key(value)
                self.legacy_keys[key].add(hid)
                evidence = Evidence(nguon="kb", ma_ban_ghi_nguon=ref, ten_goc=value, loai=kind)
                if evidence not in self.names[key]:
                    self.names[key].append(evidence)

    def _read_mock(self, mock: Path) -> None:
        for pattern in ("demo/*.json", "hoso_gia_lap/*.json"):
            for path in sorted(mock.glob(pattern)):
                case = read_json(path)
                case_ref = path.relative_to(mock).as_posix()
                known = {}
                for row in case.get("danh_muc_hoat_chat", []):
                    hid = row["hoat_chat_id"]
                    names = [(row.get("ten_quoc_te"), "inn"), (row.get("ten_hoat_chat"), "viet")]
                    known[hid] = names
                    self._add_mock(f"{case_ref}#danh_muc_hoat_chat/{hid}", names)
                for item in case.get("danh_muc_thuoc", []):
                    self._add_mock(
                        f"{case_ref}#danh_muc_thuoc/{item['thuoc_id']}",
                        [(item.get("ten_quoc_te"), "inn"), (item.get("ten_hoat_chat"), "viet")],
                    )
                    for part in item.get("thanh_phan", []):
                        hid = part.get("hoat_chat_id")
                        provided = [
                            (part.get("ten_quoc_te"), "inn"),
                            (part.get("ten_hoat_chat"), "viet"),
                        ]
                        self._add_mock(
                            f"{case_ref}#danh_muc_thuoc/{item['thuoc_id']}/{hid}",
                            [*known.get(hid, []), *provided],
                        )

    def _add_mock(self, ref: str, names: list[tuple[str | None, Literal["inn", "viet"]]]) -> None:
        for name, kind in names:
            if name and normalize_key(name):
                key = normalize_key(name)
                self.mock_groups[ref].add(key)
                evidence = Evidence(nguon="mock", ma_ban_ghi_nguon=ref, ten_goc=name, loai=kind)
                if evidence not in self.names[key]:
                    self.names[key].append(evidence)

    def _read_dav(self, stage: Path) -> None:
        conflicts = self.dav_manifest.get("so_dang_ky_trung", {})
        for row in read_jsonl(stage):
            if row["so_dang_ky"] in conflicts:
                result = SplitResult(
                    thanh_phan=[], trang_thai="chua_khop", ly_do="so_dang_ky_trung"
                )
            else:
                result = split_components(
                    row["hoat_chat_goc"], row["ham_luong_goc"], context=row["ten_thuoc"] or ""
                )
            self.dav.append((row, result))
            for part in result.thanh_phan:
                full_key = normalize_key(part.ten_hoat_chat_goc)
                # Ưu tiên tên hoặc đồng nghĩa chính xác đã có trước khi bỏ muối.
                if full_key in self.legacy_keys:
                    part.ten_chuan_hoa = full_key
                evidence = Evidence(
                    nguon="dav",
                    ma_ban_ghi_nguon=row["dav_id"],
                    ten_goc=part.ten_hoat_chat_goc,
                    loai="muoi" if part.dang_muoi else "viet",
                )
                self.names[part.ten_chuan_hoa].append(evidence)


def resolve_names(inputs: Inputs, rxnav: RxNav) -> tuple[dict[str, Match], dict[str, RxIngredient]]:
    """Ánh xạ theo thứ tự; giữ các ứng viên gần đúng trong hàng đợi."""
    matches: dict[str, Match] = {}
    identities: dict[str, RxIngredient] = {}
    legacy_rx: dict[str, set[str]] = defaultdict(set)
    exact: dict[str, tuple[RxIngredient | None, str]] = {}

    def lookup(query: str) -> tuple[RxIngredient | None, str]:
        if query not in exact:
            try:
                exact[query] = rxnav.exact(query)
            except CacheMissing:
                exact[query] = None, "thieu_dem_rxnav"
        return exact[query]

    for hid, row in inputs.legacy.items():
        if row.get("thanh_phan"):
            continue
        name = row["ten_inn"]
        query = VIET_TO_INTERNATIONAL.get(normalize_key(name), name)
        concept, _ = lookup(query)
        if concept:
            legacy_rx[concept.rxcui].add(hid)
            identities[hid] = concept

    candidates: dict[str, tuple[RxIngredient, str]] = {}
    for key, evidence in sorted(inputs.names.items()):
        legacy_keys = inputs.legacy_keys.get(key, set())
        if len(legacy_keys) == 1:
            matches[key] = Match(hoat_chat_id=next(iter(legacy_keys)), cach_khop="ma_chuan")
            continue
        if legacy_keys:
            matches[key] = Match(ly_do="ten_kb_trung_nhieu_hoat_chat")
            continue
        if key in VIET_TO_INTERNATIONAL:
            query = VIET_TO_INTERNATIONAL[key]
            targets = inputs.legacy_keys.get(normalize_key(query), set())
            if len(targets) == 1:
                matches[key] = Match(
                    hoat_chat_id=next(iter(targets)), cach_khop="bang_viet_quoc_te"
                )
                continue
        else:
            spellings = Counter(
                item.ten_goc.casefold() for item in evidence if normalize_key(item.ten_goc) == key
            )
            query = spellings.most_common(1)[0][0] if spellings else key
        concept, reason = lookup(query)
        if concept:
            candidates[key] = concept, query
        else:
            suggestions: list[Row] = []
            refs: list[str] = []
            if reason != "thieu_dem_rxnav":
                try:
                    suggestions, ref = rxnav.suggestions(query)
                    refs = sorted(
                        {ref, *(r for item in suggestions for r in item["nguon_ban_ghi_ids"])}
                    )
                except CacheMissing:
                    pass
            matches[key] = Match(ly_do=reason, goi_y=suggestions, nguon_ban_ghi_ids=refs)

    dav_ids = {
        concept.rxcui
        for key, (concept, _) in candidates.items()
        if any(item.nguon == "dav" for item in inputs.names[key])
    }
    known_ids: dict[str, set[str]] = {hid: {concept.rxcui} for hid, concept in identities.items()}
    new_ids: dict[str, set[str]] = defaultdict(set)
    for concept, _ in candidates.values():
        if concept.rxcui in dav_ids and concept.rxcui not in legacy_rx:
            new_ids[normalize_key(concept.ten_inn).replace(" ", "_")].add(concept.rxcui)
    for key, (concept, query) in candidates.items():
        refs = concept.nguon_ban_ghi_ids
        linked = legacy_rx.get(concept.rxcui, set())
        preferred = inputs.legacy_keys.get(normalize_key(query), set())
        if preferred and not linked:
            matches[key] = Match(ly_do="rxnav_khong_xac_nhan_khoa_kb", nguon_ban_ghi_ids=refs)
            continue
        if len(linked) > 1:
            matches[key] = Match(ly_do="rxcui_trung_nhieu_khoa_kb", nguon_ban_ghi_ids=refs)
            continue
        if linked:
            hid = next(iter(linked))
        else:
            hid = normalize_key(concept.ten_inn).replace(" ", "_")
            if concept.rxcui not in dav_ids:
                matches[key] = Match(ly_do="thieu_nguon_neo_dav", nguon_ban_ghi_ids=refs)
                continue
            if (
                not hid
                or hid in inputs.legacy
                or len(new_ids[hid] | known_ids.get(hid, set())) != 1
            ):
                matches[key] = Match(ly_do="xung_dot_khoa_hoat_chat", nguon_ban_ghi_ids=refs)
                continue
        identities.setdefault(hid, concept)
        method = "bang_viet_quoc_te" if key in VIET_TO_INTERNATIONAL else "rxnav_chinh_xac"
        matches[key] = Match(hoat_chat_id=hid, cach_khop=method, nguon_ban_ghi_ids=refs)
    return matches, identities


def match_counts(matches: dict[str, Match]) -> dict[str, int]:
    counts = Counter(
        value.cach_khop or ("cho_duyet_gan_dung" if value.goi_y else "chua_khop")
        for value in matches.values()
    )
    return dict(sorted(counts.items()))


def mock_unmatched(inputs: Inputs, matches: dict[str, Match]) -> list[str]:
    """Mỗi mục danh mục ca cần ít nhất một tên khớp và cùng đích."""
    missing = set()
    for keys in inputs.mock_groups.values():
        ids = {matches[key].hoat_chat_id for key in keys if matches[key].hoat_chat_id}
        if len(ids) != 1:
            missing.update(keys)
    return sorted(missing)
