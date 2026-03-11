"""
RAGナレッジソースの稼働状況確認スクリプト
MS1で9ソース中2ソースのみ稼働していた問題の調査

Usage:
    python -m scripts.check_rag_sources
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_SOURCES = [
    {
        "name": "contracts",
        "description": "契約書（メインソース）",
        "check_type": "qdrant_collection",
    },
    {
        "name": "contract_templates",
        "description": "契約テンプレート（BE4が実装）",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "template",
    },
    {
        "name": "related_contracts",
        "description": "関連契約書（staging -> 本番）",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "related_contract",
    },
    {
        "name": "user_feedback",
        "description": "ユーザーフィードバック",
        "check_type": "firestore_collection",
        "collection_name": "user_feedback",
    },
    {
        "name": "law_regulations",
        "description": "法令規制（BE3が実装）",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "law_regulation",
    },
    {
        "name": "expert_knowledge",
        "description": "専門家知見",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "expert_knowledge",
    },
    {
        "name": "benchmark_data",
        "description": "ベンチマークデータ",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "benchmark",
    },
    {
        "name": "metadata_index",
        "description": "メタデータインデックス",
        "check_type": "qdrant_metadata",
    },
    {
        "name": "ocr_results",
        "description": "OCR結果",
        "check_type": "qdrant_payload",
        "payload_key": "source_type",
        "payload_value": "ocr",
    },
]


async def check_qdrant_collection() -> Dict[str, Any]:
    """Qdrantコレクションの基本情報を取得"""
    try:
        from qdrant_client import QdrantClient

        url = os.getenv("QDRANT_URL", "")
        api_key = os.getenv("QDRANT_API_KEY", "")
        collection = os.getenv("QDRANT_COLLECTION", "conpass")

        if not url:
            return {"available": False, "error": "QDRANT_URL not configured"}

        client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        info = client.get_collection(collection)
        return {
            "available": True,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": str(info.status),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


async def check_qdrant_payload_source(
    payload_key: str, payload_value: str
) -> Dict[str, Any]:
    """Qdrantコレクション内の特定ペイロード値を持つポイント数を確認"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models

        url = os.getenv("QDRANT_URL", "")
        api_key = os.getenv("QDRANT_API_KEY", "")
        collection = os.getenv("QDRANT_COLLECTION", "conpass")

        if not url:
            return {"available": False, "error": "QDRANT_URL not configured", "count": 0}

        client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        result = client.count(
            collection_name=collection,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key=payload_key,
                        match=models.MatchValue(value=payload_value),
                    )
                ]
            ),
        )
        count = result.count
        return {
            "available": count > 0,
            "count": count,
            "error": f"ペイロード {payload_key}={payload_value} のポイントが0件"
            if count == 0
            else None,
        }
    except Exception as e:
        return {"available": False, "error": str(e), "count": 0}


async def check_qdrant_metadata() -> Dict[str, Any]:
    """Qdrantコレクション内のメタデータフィールドの存在を確認"""
    try:
        from qdrant_client import QdrantClient

        url = os.getenv("QDRANT_URL", "")
        api_key = os.getenv("QDRANT_API_KEY", "")
        collection = os.getenv("QDRANT_COLLECTION", "conpass")

        if not url:
            return {"available": False, "error": "QDRANT_URL not configured"}

        client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        # サンプルポイントを取得してメタデータフィールドを確認
        result = client.scroll(collection_name=collection, limit=5, with_payload=True)
        points, _ = result

        if not points:
            return {"available": False, "error": "コレクションにポイントがありません"}

        # メタデータフィールドの存在確認
        metadata_fields = set()
        for point in points:
            if point.payload:
                metadata_fields.update(point.payload.keys())

        expected_fields = {"contract_id", "directory_id", "text"}
        found = expected_fields.intersection(metadata_fields)
        missing = expected_fields - metadata_fields

        return {
            "available": len(found) >= 2,
            "found_fields": sorted(metadata_fields),
            "expected_found": sorted(found),
            "missing": sorted(missing) if missing else None,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


async def check_firestore_collection(collection_name: str) -> Dict[str, Any]:
    """Firestoreコレクションの存在確認"""
    try:
        from google.cloud import firestore

        project_id = os.getenv("FIRESTORE_PROJECT_ID", "")
        database_id = os.getenv("FIRESTORE_DATABASE_ID", "")

        if not project_id:
            return {"available": False, "error": "FIRESTORE_PROJECT_ID not configured"}

        db = firestore.AsyncClient(project=project_id, database=database_id)
        docs = db.collection(collection_name).limit(1)
        results = [doc async for doc in docs.stream()]
        count = len(results)
        return {
            "available": count > 0,
            "error": f"Firestoreコレクション '{collection_name}' が空またはなし"
            if count == 0
            else None,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


async def check_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """各ソースにテストクエリを投げて動作確認"""
    name = source["name"]
    check_type = source["check_type"]

    try:
        if check_type == "qdrant_collection":
            result = await check_qdrant_collection()
        elif check_type == "qdrant_payload":
            result = await check_qdrant_payload_source(
                source["payload_key"], source["payload_value"]
            )
        elif check_type == "qdrant_metadata":
            result = await check_qdrant_metadata()
        elif check_type == "firestore_collection":
            result = await check_firestore_collection(source["collection_name"])
        else:
            result = {"available": False, "error": f"不明なcheck_type: {check_type}"}
    except Exception as e:
        result = {"available": False, "error": str(e)}

    return {
        "source": name,
        "description": source["description"],
        **result,
    }


async def main():
    print("RAGソース稼働状況を確認中...\n")

    results = await asyncio.gather(*[check_source(s) for s in KNOWLEDGE_SOURCES])

    # 結果サマリー
    active = sum(1 for r in results if r.get("available"))
    total = len(results)

    # コンソール出力
    print(f"# RAGソース稼働状況レポート ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"\n稼働中: {active}/{total}\n")

    for r in results:
        status = "[OK]" if r.get("available") else "[NG]"
        print(f"  {status} {r['source']}: {r['description']}")
        if not r.get("available") and r.get("error"):
            print(f"      原因: {r['error']}")
        if r.get("count") is not None:
            print(f"      ポイント数: {r['count']}")
        if r.get("points_count") is not None:
            print(f"      総ポイント数: {r['points_count']}")
        if r.get("found_fields"):
            print(f"      メタデータフィールド: {', '.join(r['found_fields'])}")

    # Markdownレポート生成
    report_lines = [
        f"# RAGソース稼働状況レポート",
        f"",
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## サマリー",
        f"",
        f"- 稼働中: {active}/{total}",
        f"",
        f"## 各ソース詳細",
        f"",
        f"| ソース | 説明 | ステータス | 備考 |",
        f"|--------|------|----------|------|",
    ]

    for r in results:
        status_icon = "稼働中" if r.get("available") else "停止中"
        notes = ""
        if r.get("count") is not None:
            notes += f"ポイント数: {r['count']}"
        if r.get("points_count") is not None:
            notes += f"総ポイント数: {r['points_count']}"
        if not r.get("available") and r.get("error"):
            notes += f"原因: {r['error']}"
        report_lines.append(
            f"| {r['source']} | {r['description']} | {status_icon} | {notes} |"
        )

    report_lines.extend(
        [
            "",
            "## 改善アクション",
            "",
            "停止中のソースについて、以下の対応が必要:",
            "",
        ]
    )

    for r in results:
        if not r.get("available"):
            report_lines.append(f"- **{r['source']}** ({r['description']}): {r.get('error', '要調査')}")

    report_lines.append("")

    # docs/rag_source_status.md に保存
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "rag_source_status.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nレポートを保存しました: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
