"""
契約書テンプレートエンジン
Qdrant新コレクション「contract_templates」を使用し、
document_diffing_toolを拡張して条項単位の差分を実現する
"""
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.chatbot.tools.document_diffing.diff_logic import generate_diff_logic

logger = get_logger(__name__)

TEMPLATE_COLLECTION = getattr(settings, "TEMPLATE_QDRANT_COLLECTION", "contract_templates")

# 条項ラベリング基準
CLAUSE_LABELS = {
    "GREEN": "業界標準に合致。修正不要。",
    "YELLOW": "一部乖離あり。レビュー推奨。",
    "RED": "大幅な乖離あり。早急な確認が必要。",
}

# 業界標準テンプレートの初期データ定義
DEFAULT_TEMPLATES = [
    {
        "template_id": "construction_contract",
        "template_type": "工事請負契約書",
        "industry": "建設業",
        "description": "建設業向け工事請負契約の標準テンプレート",
        "clauses": [
            "工事内容・範囲", "工期", "請負代金", "支払条件",
            "変更・追加工事", "損害賠償", "契約解除", "瑕疵担保責任",
        ],
        "body": (
            "第1条（工事内容）\n本契約に基づき、受注者は以下の工事を実施する。\n\n"
            "第2条（工期）\n着工日から完工日までの期間を工期とする。\n\n"
            "第3条（請負代金）\n請負代金は金○○円とする。\n\n"
            "第4条（支払条件）\n支払は完工検収後30日以内に行う。\n\n"
            "第5条（変更・追加工事）\n工事内容の変更は書面による合意を要する。\n\n"
            "第6条（損害賠償）\n契約違反による損害は相当因果関係の範囲で賠償する。\n\n"
            "第7条（契約解除）\n重大な契約違反があった場合、相手方は契約を解除できる。\n\n"
            "第8条（瑕疵担保責任）\n受注者は引渡し後2年間、瑕疵担保責任を負う。"
        ),
    },
    {
        "template_id": "lease_agreement",
        "template_type": "賃貸借契約書",
        "industry": "不動産",
        "description": "不動産賃貸借契約の標準テンプレート",
        "clauses": [
            "物件の表示", "使用目的", "賃料・共益費", "契約期間",
            "敷金・保証金", "禁止事項", "原状回復", "契約解除",
        ],
        "body": (
            "第1条（物件の表示）\n賃貸人は以下の物件を賃借人に賃貸する。\n\n"
            "第2条（使用目的）\n賃借人は本物件を事務所用途に限り使用する。\n\n"
            "第3条（賃料・共益費）\n月額賃料は金○○円、共益費は金○○円とする。\n\n"
            "第4条（契約期間）\n契約期間は○年間とする。\n\n"
            "第5条（敷金・保証金）\n賃借人は敷金として賃料○ヶ月分を預託する。\n\n"
            "第6条（禁止事項）\n賃借人は無断転貸・改築等を行ってはならない。\n\n"
            "第7条（原状回復）\n賃借人は退去時に原状回復義務を負う。\n\n"
            "第8条（契約解除）\n賃料の3ヶ月以上の滞納は解除事由とする。"
        ),
    },
    {
        "template_id": "software_dev_contract",
        "template_type": "ソフトウェア開発委託契約書",
        "industry": "IT",
        "description": "IT業界向けソフトウェア開発委託契約の標準テンプレート",
        "clauses": [
            "委託業務の内容", "納期", "委託料", "知的財産権",
            "秘密保持", "瑕疵担保責任", "損害賠償", "契約解除",
        ],
        "body": (
            "第1条（委託業務の内容）\n委託者は受託者に対し、別紙仕様書に定めるソフトウェアの開発を委託する。\n\n"
            "第2条（納期）\n受託者は別紙に定める納期までに成果物を納入する。\n\n"
            "第3条（委託料）\n委託料は金○○円とし、検収完了後30日以内に支払う。\n\n"
            "第4条（知的財産権）\n成果物の知的財産権は検収完了時に委託者に移転する。\n\n"
            "第5条（秘密保持）\n両当事者は業務上知り得た秘密情報を第三者に開示してはならない。\n\n"
            "第6条（瑕疵担保責任）\n受託者は検収完了後1年間、瑕疵担保責任を負う。\n\n"
            "第7条（損害賠償）\n損害賠償の上限は委託料の総額とする。\n\n"
            "第8条（契約解除）\n重大な契約違反があった場合、書面による催告の上契約を解除できる。"
        ),
    },
    {
        "template_id": "nda_general",
        "template_type": "秘密保持契約書（NDA）",
        "industry": "汎用",
        "description": "汎用的な秘密保持契約のテンプレート",
        "clauses": [
            "秘密情報の定義", "秘密保持義務", "使用制限", "返還・廃棄",
            "有効期間", "損害賠償", "準拠法・管轄",
        ],
        "body": (
            "第1条（秘密情報の定義）\n秘密情報とは、開示者が受領者に対して開示する技術上・営業上の情報をいう。\n\n"
            "第2条（秘密保持義務）\n受領者は秘密情報を善良な管理者の注意をもって管理する。\n\n"
            "第3条（使用制限）\n受領者は秘密情報を本目的以外に使用してはならない。\n\n"
            "第4条（返還・廃棄）\n開示者の請求があった場合、秘密情報を速やかに返還又は廃棄する。\n\n"
            "第5条（有効期間）\n本契約の有効期間は締結日から3年間とする。\n\n"
            "第6条（損害賠償）\n秘密保持義務違反による損害を賠償する責任を負う。\n\n"
            "第7条（準拠法・管轄）\n本契約は日本法を準拠法とし、東京地方裁判所を管轄とする。"
        ),
    },
    {
        "template_id": "outsourcing_general",
        "template_type": "業務委託契約書",
        "industry": "汎用",
        "description": "汎用的な業務委託契約のテンプレート",
        "clauses": [
            "委託業務の内容", "委託期間", "委託料", "再委託",
            "秘密保持", "損害賠償", "契約解除", "反社会的勢力の排除",
        ],
        "body": (
            "第1条（委託業務の内容）\n委託者は受託者に対し、以下の業務を委託する。\n\n"
            "第2条（委託期間）\n委託期間は○年○月○日から○年○月○日までとする。\n\n"
            "第3条（委託料）\n委託料は月額金○○円とし、翌月末日までに支払う。\n\n"
            "第4条（再委託）\n受託者は委託者の事前書面承諾なく再委託を行ってはならない。\n\n"
            "第5条（秘密保持）\n両当事者は業務遂行上知り得た秘密情報を第三者に開示しない。\n\n"
            "第6条（損害賠償）\n契約違反により相手方に損害を与えた場合、賠償責任を負う。\n\n"
            "第7条（契約解除）\n重大な違反があった場合、催告の上契約を解除できる。\n\n"
            "第8条（反社会的勢力の排除）\n各当事者は反社会的勢力でないことを表明保証する。"
        ),
    },
]


class TemplateService:
    """契約書テンプレートエンジン"""

    COLLECTION_NAME = TEMPLATE_COLLECTION

    def __init__(self):
        self._qdrant_url = settings.QDRANT_URL
        self._qdrant_api_key = settings.QDRANT_API_KEY

    def _get_qdrant_client(self):
        from qdrant_client import QdrantClient
        return QdrantClient(url=self._qdrant_url, api_key=self._qdrant_api_key)

    async def compare_with_template(
        self,
        contract_id: str,
        template_type: Optional[str] = None,
        conpass_jwt: Optional[str] = None,
    ) -> dict:
        """
        契約書をテンプレートと比較し、条項ごとの差分・ラベリングを返す。

        1. 契約書テキスト取得（ConPass API）
        2. テンプレート取得（Qdrant contract_templates コレクション）
        3. document_diffing で差分検出
        4. 各条項を GREEN/YELLOW/RED でラベリング
        """
        try:
            # 1. 契約書テキストを取得
            from app.services.conpass_api_service import ConpassApiService

            if not conpass_jwt:
                return {"error": "conpass_jwt is required to fetch contract text"}

            api_service = ConpassApiService(conpass_jwt=conpass_jwt)
            contract_text = await api_service.get_contract_body_text(int(contract_id))
            if not contract_text:
                return {"error": f"Contract {contract_id} body text not found"}

            # 2. テンプレートを取得
            template = await self._find_template(template_type)
            if not template:
                return {
                    "error": f"Template not found for type: {template_type}",
                    "available_templates": await self.list_templates(),
                }

            template_body = template.get("body", "")

            # 3. document_diffing で差分検出
            diff_data = {
                f"contract_{contract_id}": contract_text,
                f"template_{template.get('template_id', 'unknown')}": template_body,
            }
            diff_instruction = (
                "契約書とテンプレートを条項ごとに比較してください。"
                "各条項について以下を判定してください:\n"
                "- GREEN: 業界標準に合致。修正不要。\n"
                "- YELLOW: 一部乖離あり。レビュー推奨。\n"
                "- RED: 大幅な乖離あり。早急な確認が必要。\n"
                "条項ごとにラベルと理由を明記してください。"
            )
            diff_result = await generate_diff_logic(diff_data, diff_instruction)

            return {
                "contract_id": contract_id,
                "template_id": template.get("template_id"),
                "template_type": template.get("template_type"),
                "diff_result": diff_result,
                "clause_labels_legend": CLAUSE_LABELS,
            }
        except Exception as e:
            logger.exception(f"Template comparison error: {e}")
            return {"error": str(e)}

    async def _find_template(self, template_type: Optional[str] = None) -> Optional[dict]:
        """Qdrantからテンプレートを検索する"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            client = self._get_qdrant_client()

            conditions = []
            if template_type:
                conditions.append(
                    FieldCondition(
                        key="template_type",
                        match=MatchValue(value=template_type),
                    )
                )

            scroll_filter = Filter(must=conditions) if conditions else None
            response = client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            points, _ = response
            if points:
                return points[0].payload
            return None
        except Exception as e:
            logger.warning(f"Qdrant template search failed: {e}")
            # フォールバック: デフォルトテンプレートから検索
            for t in DEFAULT_TEMPLATES:
                if template_type and t["template_type"] == template_type:
                    return t
            return DEFAULT_TEMPLATES[0] if DEFAULT_TEMPLATES else None

    async def list_templates(
        self,
        industry: Optional[str] = None,
        contract_type: Optional[str] = None,
    ) -> list[dict]:
        """利用可能なテンプレート一覧を返す"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            client = self._get_qdrant_client()

            conditions = []
            if industry:
                conditions.append(
                    FieldCondition(key="industry", match=MatchValue(value=industry))
                )
            if contract_type:
                conditions.append(
                    FieldCondition(
                        key="template_type", match=MatchValue(value=contract_type)
                    )
                )

            scroll_filter = Filter(must=conditions) if conditions else None
            response = client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            points, _ = response

            templates = []
            for p in points:
                payload = p.payload or {}
                templates.append({
                    "template_id": payload.get("template_id"),
                    "template_type": payload.get("template_type"),
                    "industry": payload.get("industry"),
                    "description": payload.get("description"),
                    "clauses": payload.get("clauses", []),
                })
            return templates
        except Exception as e:
            logger.warning(f"Qdrant template list failed, using defaults: {e}")
            # フォールバック: デフォルトテンプレートを返す
            results = []
            for t in DEFAULT_TEMPLATES:
                if industry and t["industry"] != industry:
                    continue
                if contract_type and t["template_type"] != contract_type:
                    continue
                results.append({
                    "template_id": t["template_id"],
                    "template_type": t["template_type"],
                    "industry": t["industry"],
                    "description": t["description"],
                    "clauses": t["clauses"],
                })
            return results

    async def seed_default_templates(self) -> dict:
        """業界標準テンプレートの初期データをQdrantに投入する"""
        try:
            from qdrant_client.models import Distance, VectorParams, PointStruct
            import uuid

            client = self._get_qdrant_client()

            # コレクションが存在しない場合は作成
            collections = client.get_collections().collections
            collection_names = [c.name for c in collections]
            if self.COLLECTION_NAME not in collection_names:
                embedding_dim = settings.EMBEDDING_DIM or 1024
                client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=embedding_dim, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.COLLECTION_NAME}")

            # テンプレートデータを投入
            points = []
            for template in DEFAULT_TEMPLATES:
                embedding_dim = settings.EMBEDDING_DIM or 1024
                # ダミーベクトル（seed時はベクトル検索を使わないため）
                dummy_vector = [0.0] * embedding_dim
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=dummy_vector,
                    payload=template,
                )
                points.append(point)

            client.upsert(collection_name=self.COLLECTION_NAME, points=points)
            logger.info(f"Seeded {len(points)} templates to {self.COLLECTION_NAME}")

            return {
                "success": True,
                "message": f"{len(points)} templates seeded",
                "templates": [t["template_id"] for t in DEFAULT_TEMPLATES],
            }
        except Exception as e:
            logger.exception(f"Template seed error: {e}")
            return {"success": False, "error": str(e)}
