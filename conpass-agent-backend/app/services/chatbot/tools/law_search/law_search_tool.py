"""
法令×契約書 コンプライアンスリスク検出ツール

処理フロー:
  1. ユーザーが挙げた法令名で conpass_laws を検索 → 関連条文を取得
  2. 各条文テキストで conpass（契約書）を並列検索 → 候補契約を収集
  3. LLM が各候補契約 × 法令要件を評価 → HIGH/MEDIUM/LOW/COMPLIANT を判定
  4. HIGH/MEDIUM/LOW を返却（COMPLIANT のみ除外）
"""
import asyncio
import logging
from typing import Optional, List, Literal

from pydantic import BaseModel
from llama_index.core.tools import FunctionTool

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

LAW_SCORE_THRESHOLD      = 0.30   # 法令条文検索（見逃し防止のため低め）
CONTRACT_SCORE_THRESHOLD = 0.40   # 契約候補検索（広めに取ってLLMで絞り込む）
MAX_CANDIDATE_CONTRACTS  = 15     # LLM評価の上限


# ── Pydantic モデル ──────────────────────────────────────────────────────────

class ComplianceGap(BaseModel):
    article_number: str      # 関連する条文番号（例: 第3条）
    requirement: str         # 法令が求める内容（1〜2文）
    gap_description: str     # 何が不足・不明確か（具体的に）
    contract_reference: str  # 契約書の該当テキスト（なければ空文字）


class ComplianceEvaluation(BaseModel):
    risk_level: Literal["HIGH", "MEDIUM", "LOW", "COMPLIANT"]
    gaps: List[ComplianceGap]
    summary: str             # 総評（1〜2文）


# ── 検索関数 ─────────────────────────────────────────────────────────────────

async def _search_laws(
    query: str,
    law_name_filter: Optional[str],
    top_k: int = 10,
) -> List[dict]:
    """conpass_laws コレクションをハイブリッド検索"""
    from llama_index.core.settings import Settings as LlamaSettings
    from app.services.chatbot.tools.semantic_search.sparse_query import get_sparse_embedding_model
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Prefetch, Filter, FieldCondition, MatchText, FusionQuery, Fusion
    )

    laws_collection = settings.QDRANT_LAWS_COLLECTION
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)

    embed_model  = LlamaSettings.embed_model
    sparse_model = get_sparse_embedding_model()

    loop = asyncio.get_running_loop()
    dense_vec  = await loop.run_in_executor(None, embed_model.get_text_embedding, query)
    sparse_emb = list(sparse_model.embed([query]))[0]

    filter_cond = None
    if law_name_filter:
        filter_cond = Filter(
            should=[
                FieldCondition(key="law_name",       match=MatchText(text=law_name_filter)),
                FieldCondition(key="law_short_name", match=MatchText(text=law_name_filter)),
            ]
        )

    from qdrant_client.models import SparseVector

    # 短い断片が多い法令（施行規則等）対応: 多めに取得してフィルタリング
    fetch_limit = top_k * 5

    response = client.query_points(
        collection_name=laws_collection,
        prefetch=[
            Prefetch(
                query=list(dense_vec),
                using="dense",
                limit=fetch_limit,
                score_threshold=LAW_SCORE_THRESHOLD,
                filter=filter_cond,
            ),
            Prefetch(
                query=SparseVector(
                    indices=[int(x) for x in sparse_emb.indices],
                    values=[float(x) for x in sparse_emb.values],
                ),
                using="sparse",
                limit=fetch_limit,
                filter=filter_cond,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=fetch_limit,
        with_payload=True,
        with_vectors=False,
    )

    # 50文字未満の断片（条文番号の相互参照のみ）は除外し、有効な条文のみ返す
    MIN_ARTICLE_LEN = 50
    valid = [
        pt.payload for pt in response.points
        if pt.payload and len((pt.payload.get("text") or "").strip()) >= MIN_ARTICLE_LEN
    ]
    logger.info(
        f"[LawSearch] 条文取得: 全{len(response.points)}件 → "
        f"有効({MIN_ARTICLE_LEN}文字以上){len(valid)}件"
    )
    return valid[:top_k]


async def _search_contracts_by_article(
    article_text: str,
    directory_ids: List[int],
    top_k: int = 5,
) -> List[dict]:
    """条文テキストで契約書コレクションをセマンティック検索"""
    from llama_index.core.settings import Settings as LlamaSettings
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchAny

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)
    embed_model = LlamaSettings.embed_model

    loop = asyncio.get_running_loop()
    dense_vec = await loop.run_in_executor(None, embed_model.get_text_embedding, article_text[:800])

    query_filter = None
    if directory_ids:
        query_filter = Filter(must=[
            FieldCondition(key="directory_id", match=MatchAny(any=directory_ids))
        ])

    response = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=list(dense_vec),
        using="dense",
        query_filter=query_filter,
        limit=top_k,
        score_threshold=CONTRACT_SCORE_THRESHOLD,
        with_payload=True,
        with_vectors=False,
    )

    seen = set()
    contracts = []
    for pt in response.points:
        payload = pt.payload or {}
        cid = payload.get("contract_id")
        if cid and cid not in seen:
            seen.add(cid)
            contracts.append({
                "contract_id":   cid,
                "title":         payload.get("契約書名_title") or payload.get("name", f"契約書#{cid}"),
                "company_a":     payload.get("会社名_甲_company_a", ""),
                "company_b":     payload.get("会社名_乙_company_b", ""),
                "matching_text": (payload.get("text") or "").strip()[:400],
            })
    return contracts


async def _fetch_contract_chunks(
    contract_id: int,
    directory_ids: List[int],
    max_chunks: int = 8,
) -> List[str]:
    """
    指定した contract_id の複数チャンクを取得する。
    冒頭（前文・当事者・目的）+ 中盤チャンクを幅広く取得し、LLM に渡す。
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)

    must_conditions = [FieldCondition(key="contract_id", match=MatchValue(value=contract_id))]
    if directory_ids:
        must_conditions.append(
            FieldCondition(key="directory_id", match=MatchAny(any=directory_ids))
        )

    result, _ = client.scroll(
        collection_name=settings.QDRANT_COLLECTION,
        scroll_filter=Filter(must=must_conditions),
        limit=max_chunks,
        with_payload=True,
        with_vectors=False,
    )

    texts = []
    for pt in result:
        t = ((pt.payload or {}).get("text") or "").strip()
        if t:
            texts.append(t[:500])
    return texts


# ── LLM 適合性評価 ──────────────────────────────────────────────────────────

async def _evaluate_contract_compliance(
    law_name: str,
    articles: List[dict],
    contract_id: int,
    contract_texts: List[str],
) -> Optional[ComplianceEvaluation]:
    """
    LLM を使って法令要件と契約内容の適合性を評価する。
    エラー・タイムアウト時は None を返す。
    """
    from llama_index.llms.openai import OpenAIResponses

    if not contract_texts:
        return None

    # 法令条文テキストを整形（最大5条文 × 400文字）
    # 50文字以上の有効な条文のみ使用
    article_lines = []
    for a in articles[:5]:
        text = (a.get("text") or "").strip()
        if len(text) < 50:
            continue  # 断片は除外
        num = a.get("article_number", "（条文番号なし）")
        article_lines.append(f"{num}:\n{text[:400]}")
    articles_block = "\n\n".join(article_lines) or "（有効な条文テキストが取得できませんでした）"

    # デバッグ: LLMに渡す内容をログ出力
    logger.info(
        f"[LawSearch] LLM入力 cid={contract_id} | "
        f"条文{len(article_lines)}件 | 契約テキスト{len(contract_texts)}チャンク"
    )
    logger.info(f"[LawSearch] 条文内容(先頭200字): {articles_block[:200]}")
    logger.info(f"[LawSearch] 契約テキスト(先頭200字): {(contract_texts[0] if contract_texts else '')[:200]}")

    # 契約書チャンクを整形（最大8チャンク）
    contract_block = "\n\n---\n\n".join(contract_texts[:8]) or "（契約書テキストなし）"

    prompt = f"""あなたは産業廃棄物・法令コンプライアンスの専門家です。
以下の手順で**厳密に**評価してください。

【ステップ1: 文書種別の確認（最優先）】
「契約書テキスト」が企業間のビジネス契約書かどうか確認してください。
以下に該当する場合のみ COMPLIANT を返してください（評価対象外として）:
- 在留カード・パスポート・免許証などの身分証明書
- 領収書・請求書・納品書・名刺・履歴書
- OCR エラーや意味不明なテキストのみの文書

【ステップ2: チェックリスト評価（ビジネス契約書の場合）】
法令「{law_name}」に関して、以下の2点を**それぞれ個別に**検証してください。

━━ A. 法令が要求する必須記載事項の確認 ━━
下記の関連条文に記載された各項目（一、二、三...と番号付きの事項）について、
契約書テキストに**明示的に記載されているか**を一つずつ確認してください。

【関連条文】
{articles_block}

【契約書テキスト】
{contract_block}

各番号付き項目の確認:
- 「廃棄物の種類」が「一式」「廃棄物全般」など曖昧な記載 → **HIGH**（具体的種類の記載が義務）
- 「必要に応じて」「任意で」など任意表現で義務事項を規定 → **HIGH**（義務を任意化は違反）
- 許可証の事業範囲が契約書に明記されていない → **HIGH**
- 廃棄物の性状・荷姿・取扱注意事項の記載なし → **HIGH**
- 項目が抜粋に見当たらない → **MEDIUM**（全文確認が必要）

━━ B. 禁止行為・違法条項の確認 ━━
契約書テキストに以下のような**法令違反となる条項**が含まれていないか確認してください:
- 「事前承諾なく再委託できる」「無断で再委託」→ **HIGH**（産業廃棄物の再委託は原則禁止・書面承諾必須）
- 「必要に応じてマニフェストを交付」→ **HIGH**（マニフェスト交付は全廃棄物輸送で義務）
- 「処理方法は受託者に一任」→ **HIGH**（具体的処理方法の記載が義務）
- 法令が定める数値・期限の超過 → **HIGH**

【最終判定基準】
- HIGH: A または B のいずれかで1つ以上の重大な不備・違反が確認された
- MEDIUM: 重大な違反はないが、不明確・判断困難な項目がある
- LOW: 実質的には問題ないが軽微な不明確点がある
- COMPLIANT: 全必須項目が明示され、禁止行為もない（または評価対象外文書）

COMPLIANT の場合のみ gaps を空リストにすること"""

    try:
        llm = OpenAIResponses(
            model="gpt-4o-mini",
            temperature=0.2,
            api_key=settings.OPENAI_API_KEY,
            timeout=60,
            max_retries=1,
        )
        sllm = llm.as_structured_llm(ComplianceEvaluation)
        response = await asyncio.wait_for(sllm.acomplete(prompt), timeout=65.0)
        result = response.raw
        logger.info(
            f"[LawSearch] LLM評価: cid={contract_id} risk={result.risk_level} "
            f"gap_count={len(result.gaps)}"
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[LawSearch] LLM評価タイムアウト: cid={contract_id}")
        return None
    except Exception as e:
        logger.warning(f"[LawSearch] LLM評価エラー: cid={contract_id}: {e}")
        return None


# ── メイン検索ロジック ────────────────────────────────────────────────────────

async def _law_search_async(
    query: str,
    law_name: Optional[str],
    directory_ids: Optional[List[int]],
) -> str:
    """法令×契約書 コンプライアンスリスク検出（非同期）"""

    # Step 1: 関連条文を取得（メイン検索 + 委託契約要件の補完検索を並行実行）
    law_label = law_name or "法令"
    supplementary_query = f"{law_label} 委託契約 記載事項 義務 許可 要件"

    articles_main, articles_sup = await asyncio.gather(
        _search_laws(query, law_name),
        _search_laws(supplementary_query, law_name, top_k=5),
    )

    # メイン結果 + 補完結果をマージ（重複除去・50文字以上のみ）
    seen_texts: set = set()
    articles: List[dict] = []
    for a in articles_main + articles_sup:
        snippet = (a.get("text") or "")[:80]
        if snippet and snippet not in seen_texts and len(a.get("text","")) >= 50:
            articles.append(a)
            seen_texts.add(snippet)

    logger.info(
        f"[LawSearch] 条文ヒット数: {len(articles)} "
        f"(main={len(articles_main)}, sup={len(articles_sup)}), law_name={law_name}"
    )
    if not articles:
        return (
            f"「{law_name or query}」に関する法令がシステムに登録されていません。"
            "管理者に法令の登録を依頼してください。"
        )

    # Step 2: 各条文で契約書を並列検索 → 候補契約を収集
    search_tasks = [
        _search_contracts_by_article(article.get("text", ""), directory_ids or [])
        for article in articles
    ]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    contract_to_info: dict = {}
    for article, contract_list in zip(articles, results):
        if isinstance(contract_list, Exception):
            logger.warning(f"[LawSearch] contract search failed: {contract_list}")
            continue
        for c in contract_list:
            cid = c["contract_id"]
            if cid not in contract_to_info:
                contract_to_info[cid] = {
                    "title":          c["title"],
                    "company_a":      c["company_a"],
                    "company_b":      c["company_b"],
                    "articles":       [],
                    "contract_texts": [],
                }
            art_num = article.get("article_number") or ""
            if art_num and art_num not in contract_to_info[cid]["articles"]:
                contract_to_info[cid]["articles"].append(art_num)
            mt = c["matching_text"]
            if mt and mt not in contract_to_info[cid]["contract_texts"]:
                contract_to_info[cid]["contract_texts"].append(mt)

    candidate_count = len(contract_to_info)
    logger.info(f"[LawSearch] 候補契約数: {candidate_count}件")
    if not contract_to_info:
        return "条文要件に該当する候補契約が見つかりませんでした。"

    # 最大 MAX_CANDIDATE_CONTRACTS 件に制限
    candidate_ids = list(contract_to_info.keys())[:MAX_CANDIDATE_CONTRACTS]
    law_full_name = articles[0].get("law_name", law_label) if articles else law_label

    # Step 2.5: 候補契約ごとに複数チャンクを取得（並列）
    chunk_tasks = [
        _fetch_contract_chunks(cid, directory_ids or [])
        for cid in candidate_ids
    ]
    chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
    for cid, chunks in zip(candidate_ids, chunk_results):
        if isinstance(chunks, list) and chunks:
            # マッチングテキストと合わせて重複除去しながら追加
            existing = set(contract_to_info[cid]["contract_texts"])
            for ch in chunks:
                if ch and ch not in existing:
                    contract_to_info[cid]["contract_texts"].append(ch)
                    existing.add(ch)
    logger.info(f"[LawSearch] 複数チャンク取得完了")

    # Step 3: 各候補契約を LLM で評価（並列）
    eval_tasks = []
    for cid in candidate_ids:
        info = contract_to_info[cid]
        # その契約に紐づく条文を取得（条文番号が一致するもの、なければ全条文）
        relevant_articles = [
            a for a in articles
            if (a.get("article_number") or "") in info["articles"]
        ] or articles[:3]
        eval_tasks.append(
            _evaluate_contract_compliance(
                law_name=law_label,
                articles=relevant_articles,
                contract_id=cid,
                contract_texts=info["contract_texts"],
            )
        )

    evaluations = await asyncio.gather(*eval_tasks, return_exceptions=True)

    # Step 4: HIGH/MEDIUM のみ残す（LOW・COMPLIANT は除外）
    risk_contracts = []
    for cid, ev in zip(candidate_ids, evaluations):
        if isinstance(ev, ComplianceEvaluation) and ev.risk_level in ("HIGH", "MEDIUM"):
            risk_contracts.append((cid, ev))

    risk_count = len(risk_contracts)
    logger.info(
        f"[LawSearch] リスク契約: {risk_count}件 / 候補 {len(candidate_ids)}件を評価"
    )

    if not risk_contracts:
        return (
            f"## {law_label}に関するコンプライアンスリスク評価結果\n\n"
            f"候補 {len(candidate_ids)} 件の契約を LLM で評価しましたが、"
            f"「{law_full_name}」の要件を満たしていない可能性がある契約は検出されませんでした。\n\n"
            "**※ これは検索対象の範囲内での結果です。法令テキストと意味的に遠い契約は評価対象外です。**"
        )

    # Step 5: 結果フォーマット
    risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    lines = [
        f"## {law_label}の要件を満たしていない可能性がある契約書（{risk_count}件 / 候補{len(candidate_ids)}件を評価）",
        "",
        f"登録法令「{law_full_name}」の条文と契約書を LLM で照合し、**不適合・不明確と判定した契約のみ**を表示しています。",
        "🔴 HIGH = 明らかな要件不足・違反　🟡 MEDIUM = 不明確・要全文確認",
        "COMPLIANT（適合）と判定された契約は除外しています。",
        "",
        "---",
        "",
    ]

    for idx, (cid, ev) in enumerate(risk_contracts, 1):
        info          = contract_to_info[cid]
        contract_url  = f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{cid}"
        title         = info["title"]
        company_a     = info["company_a"]
        company_b     = info["company_b"]
        emoji         = risk_emoji.get(ev.risk_level, "⚪")

        lines.append(f"### {idx}. 契約ID #{cid}　{title}")
        lines.append(f"**リスクレベル: {emoji} {ev.risk_level}**")
        if company_a or company_b:
            lines.append(f"**当事者**: {company_a} × {company_b}")
        lines.append(f"**契約URL**: {contract_url}")
        lines.append("")

        if ev.gaps:
            lines.append("**▼ 法令要件と不足点**")
            for gap in ev.gaps:
                art_num = gap.article_number or "（条文番号なし）"
                lines.append(f"**{art_num}**")
                lines.append(f"- 法令要件: {gap.requirement}")
                lines.append(f"- 不足点: {gap.gap_description}")
                if gap.contract_reference:
                    lines.append(f"- 契約書の現状: 「{gap.contract_reference}」")
                else:
                    lines.append("- 契約書の現状: 該当条項が見当たらない")
                lines.append("")

        lines.append(f"**▼ 総評**")
        lines.append(ev.summary)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(
        f"**※ {len(candidate_ids)}件の候補契約を LLM で評価し、HIGH/MEDIUM リスクの{risk_count}件を表示。"
        "LOW（実質問題なし）・COMPLIANT（適合）と判定された契約は表示していません。"
        "法的な最終判断は専門家にご確認ください。**"
    )
    return "\n".join(lines)


# ── FunctionTool ────────────────────────────────────────────────────────────

def get_law_search_tool(directory_ids: List[int]) -> FunctionTool:
    """
    法令要件と契約書をクロス検索し、コンプライアンスリスクを評価するツールを返す。

    Args:
        directory_ids: 検索対象ディレクトリIDリスト
    """

    async def law_search(
        query: str,
        law_name: Optional[str] = None,
    ) -> str:
        """
        登録された法令の要件と契約書を照合し、要件を満たしていない可能性がある契約を返す。

        「〇〇法に影響を受ける契約を探して」「取適法の条文に照らした契約チェック」など
        法令準拠の確認が必要なときに使用する。

        Args:
            query: 検索クエリ（例: "取適法に影響を受ける契約"）
            law_name: 特定の法令名でフィルタ（例: "取適法", "下請法"）精度向上に有効
        """
        try:
            return await _law_search_async(query, law_name, directory_ids)
        except Exception as e:
            logger.error(f"[LawSearch] error: {e}", exc_info=True)
            return f"法令検索中にエラーが発生しました: {e}"

    return FunctionTool.from_defaults(
        async_fn=law_search,
        name="law_search",
        description=(
            "登録された法令・規制の条文と契約書を LLM で照合し、"
            "コンプライアンスリスク（要件不足・不明確）がある契約を特定するツール。\n\n"
            "【使用すべき場面】\n"
            "- 「〇〇法に影響を受ける契約は？」「〇〇法の観点で問題になりうる契約は？」\n"
            "- 「取適法の条文に照らした契約チェック」「法令準拠の確認」\n"
            "- 「このまま放置すると指摘を受けるリスクがある契約は？」\n\n"
            "【重要：ユーザーの意図の理解】\n"
            "法令の影響を受ける契約の問い合わせは「監督機関や取引先から法令違反を指摘される"
            "可能性がある契約を事前に把握したい」というコンプライアンスリスク確認の意図がある。\n\n"
            "【出力の扱い】\n"
            "このツールは LLM がリスクと判定した契約のみを返す。"
            "COMPLIANT（適合）と判定された契約は含まれない。"
            "AIは結果を要約・選択せず、ツールが返した全件をそのままユーザーに提示すること。\n\n"
            "【パラメータ】\n"
            "law_name に法令の略称（例: 取適法, 下請法）を渡すと精度が上がる。"
            "法令がシステムに登録されていない場合はその旨を返す。"
        ),
    )
