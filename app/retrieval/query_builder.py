"""Truy vấn theo mẫu cố định, không dùng văn bản ca bệnh."""

from app.config.settings import RetrievalSettings
from app.core.types import RetrievalQuery, SearchFilter

_TEMPLATES: dict[int, tuple[list[str], str, str]] = {
    1: (
        ["chong_chi_dinh", "canh_bao"],
        "{vi} dị ứng quá mẫn chống chỉ định phản ứng chéo",
        "{en} hypersensitivity contraindication cross-reactivity allergy",
    ),
    3: (
        ["chi_dinh", "lieu"],
        "{vi} chỉ định liều dùng đường dùng",
        "{en} indications dosage and administration",
    ),
    4: (["tuong_tac"], "{vi} tương tác thuốc", "{en} drug interactions"),
    5: (
        ["canh_bao", "tac_dung_phu"],
        "{vi} cảnh báo độc tính tác dụng không mong muốn",
        "{en} warnings toxicity adverse reactions",
    ),
    6: (
        ["lieu_than", "lieu_gan", "lieu", "thai_ky_cho_bu", "nhi_cao_tuoi"],
        "{vi} chỉnh liều suy thận độ thanh thải creatinin",
        "{en} renal impairment dosage adjustment creatinine clearance",
    ),
}


class QueryBuilder:
    """Sinh truy vấn Việt và Anh theo thứ tự ngôn ngữ cấu hình."""

    def __init__(self, settings: RetrievalSettings) -> None:
        self.settings = settings

    def for_finding(
        self,
        hoat_chat_id: str,
        ten_inn: str,
        ten_viet: str,
        yeu_to: int,
        ma_luat: str | None,
    ) -> RetrievalQuery:
        """Chỉ dùng hoạt chất và mẫu của yếu tố, không ghép nội dung phát hiện."""
        sections, vi, en = _TEMPLATES.get(yeu_to, ([], "{vi}", "{en}"))
        templates = {"vi": vi, "en": en}
        return RetrievalQuery(
            van_ban=[
                templates[language].format(vi=ten_viet, en=ten_inn)
                for language in self.settings.query_languages
            ],
            bo_loc=SearchFilter(
                hoat_chat_ids=[hoat_chat_id], nhom_nguon="nhan_thuoc", muc=list(sections)
            ),
            k_query=self.settings.nhan_thuoc.k_query,
            k_rerank=self.settings.nhan_thuoc.k_rerank,
        )

    def baseline(self, hoat_chat_id: str, ten_inn: str, ten_viet: str) -> list[RetrievalQuery]:
        """Luôn truy vấn chống chỉ định và tương tác cho mỗi hoạt chất."""
        return [
            self.for_finding(hoat_chat_id, ten_inn, ten_viet, factor, None) for factor in (1, 4)
        ]
