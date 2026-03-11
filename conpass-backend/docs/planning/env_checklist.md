# ConPass 開発環境 セットアップチェックリスト

作成日: 2026-02-20

---

## 1. プロジェクト構成概要

| リポジトリ | 技術スタック | Python | パッケージ管理 |
|---|---|---|---|
| conpass-backend | Django 3.2 + DRF + Celery + MySQL | 3.8 | Pipenv |
| conpass-agent-backend | FastAPI + LlamaIndex/OpenAI + Qdrant | 3.12 | uv (pyproject.toml + uv.lock) |

---

## 2. Docker Compose サービス一覧 (conpass-backend)

| サービス | イメージ/ビルド | ポート (ホスト:コンテナ) | 説明 |
|---|---|---|---|
| app | カスタム (Dockerfile) | 1717:1717 | Django API (uWSGI) |
| worker | app と同じイメージ | 8806:8000 | Celery Worker + Supervisord |
| worker2 | app と同じイメージ | 1718:1718 | 追加 uWSGI ワーカー |
| web | カスタム (Nginx) | **8800:80** | Nginx フロントプロキシ |
| db | カスタム (MySQL) | **8802:3306** | MySQL データベース |
| redis | redis (公式) | **8803:6379** | Redis (Celery ブローカー/キャッシュ) |
| maildev | ykanazawa/sendgrid-maildev | **8804:1080**, **8805:3030** | SendGrid 開発メールサーバー |
| keycloak | quay.io/keycloak/keycloak:18.0.0 | **18080:8080** | SSO/SAML IdP (Keycloak) |

### conpass-agent-backend

- Docker Compose ファイルなし (単体 Dockerfile のみ)
- ポート: **8080** (uvicorn)
- ローカル開発時は `uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload` で起動

---

## 3. 必須環境変数一覧

### 3.1 conpass-backend (.env)

#### ローカルで設定不要 (Docker Compose で自動設定)

| 変数 | デフォルト値 | 備考 |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.local` | |
| `LOG_LEVEL` | `INFO` | |
| `DB_HOST` | `db` | Docker サービス名 |
| `DB_PORT` | `3306` | |
| `DB_DATABASE` | `conpass` | |
| `DB_USER` | `conpass` | |
| `DB_PASSWORD` | `secret` | |
| `REDIS_URL` | `redis://redis:6379/1` | |
| `PRIVATE_API_URL` | `http://localhost:8806` | |
| `UPLOAD_PDF_FILE_SIZE_MAX` | `104857600` (100MB) | |
| `CLEANUP_PERIOD_FOR_FAILED_UPLOADS_SECONDS` | `172800` | |
| `VUE_APP_LOCAL_MODE` | `false` | |
| `SENDGRID_DEV_HOST` | `http://maildev:3030` | MailDev 経由 |
| `SSO_SAML_SP_*` | localhost 向け設定済み | |

#### 外部APIキーが必要 (要設定)

| 変数 | サービス | 必須度 | 備考 |
|---|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP 全般 | **必須** | サービスアカウントキーの JSON ファイルパス |
| `GCP_PREDICTION_MODEL_NAME` | GCP AutoML | 任意 | 文書分類 AI モデル |
| `GCS_BUCKET_NAME_API` | GCS | **必須** | API データバケット |
| `GCS_BUCKET_NAME_FILE` | GCS | **必須** | ファイルデータバケット |
| `GCS_BUCKET_NAME_WEB` | GCS | **必須** | Web ファイルバケット |
| `GCS_BUCKET_NAME_NATURAL_LANGUAGE` | GCS | 任意 | NL データセット |
| `AZURE_LANGUAGE_ENDPOINT` | Azure AI Text Analytics | 任意 | エンティティ抽出 |
| `AZURE_LANGUAGE_KEY` | Azure AI Text Analytics | 任意 | |
| `GV_ENTITY_EXTRACTION_GPT_ENDPOINT` | GrowthVerse (Cloud Functions) | 任意 | GPT エンティティ抽出 |
| `GV_OCR_GEMINI_ENDPOINT` | GrowthVerse (Cloud Functions) | 任意 | Gemini OCR |
| `VUE_APP_TINY_MCE_API_KEY` | TinyMCE | 任意 | フロント WYSIWYG エディタ |
| `VUE_APP_FIREBASE_CONFIG` | Firebase | 任意 | |
| `SENDGRID_API_KEY` | SendGrid | 任意* | *MailDev 使用時は不要 |
| `ADOBESIGN_APPLICATION_ID` | Adobe Sign | 任意 | 電子署名 |
| `ADOBESIGN_APPLICATION_SECRET` | Adobe Sign | 任意 | |

### 3.2 conpass-agent-backend (.env)

#### ローカルで設定可 (デフォルト/ダミー値で動作可能)

| 変数 | デフォルト値 | 備考 |
|---|---|---|
| `ALLOWED_ORIGINS` | `*` | |
| `CHUNK_OVERLAP` | `100` | |
| `CHUNK_SIZE` | `1024` | |
| `EMBEDDING_DIM` | `1024` | |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | |
| `MODEL` | `gpt-4o-mini` | |
| `MODEL_PROVIDER` | `openai` | |
| `LLM_TEMPERATURE` | `0.3` | |
| `ENVIRONMENT` | `development` | |
| `FILESERVER_URL_PREFIX` | `http://localhost:8000/api/files` | |

#### 外部APIキーが必要 (要設定)

| 変数 | サービス | 必須度 | 備考 |
|---|---|---|---|
| `OPENAI_API_KEY` | OpenAI | **必須** | LLM + Embedding |
| `GOOGLE_AI_API_KEY` | Google AI (Gemini) | 任意 | MODEL_PROVIDER=google 時のみ |
| `QDRANT_URL` | Qdrant Cloud | **必須** | ベクトル DB |
| `QDRANT_API_KEY` | Qdrant Cloud | **必須** | |
| `QDRANT_COLLECTION` | Qdrant | **必須** | コレクション名 |
| `CONPASS_API_BASE_URL` | ConPass Backend | **必須** | Django API ベース URL |
| `CONPASS_FRONTEND_BASE_URL` | ConPass Frontend | **必須** | |
| `CONPASS_JWT_SECRET` | JWT | **必須** | Backend と共有する JWT シークレット |
| `FIRESTORE_PROJECT_ID` | Firestore | **必須** | チャット履歴保存 |
| `FIRESTORE_DATABASE_ID` | Firestore | **必須** | |
| `GCS_BUCKET_NAME` | GCS | **必須** | ファイル配信 |
| `CDN_DOMAIN` | CDN | **必須** | |
| `REDIS_URL` | Redis | **必須** | |
| `GOOGLE_CLOUD_PROJECT_ID` | Document AI | 任意 | OCR 用 |
| `DOCUMENT_AI_PROCESSOR_ID` | Document AI | 任意 | |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP | 任意 | Document AI 用 |
| `LANGFUSE_HOST` | Langfuse | 任意 | オブザーバビリティ |
| `LANGFUSE_PUBLIC_KEY` | Langfuse | 任意 | |
| `LANGFUSE_SECRET_KEY` | Langfuse | 任意 | |

---

## 4. 外部サービス依存一覧とモック方針

| 外部サービス | 使用箇所 | モック方針 |
|---|---|---|
| **GCP Cloud Storage** | ファイルアップロード/ダウンロード | ローカルファイルシステム or `fake-gcs-server` Docker |
| **GCP Vision API** | OCR/文書スキャン | pytest mock (既存テストで対応済みの可能性大) |
| **GCP AutoML** | 文書分類予測 | pytest mock |
| **Azure AI Text Analytics** | エンティティ抽出 | pytest mock |
| **SendGrid** | メール送信 | **MailDev (Docker Compose に含まれる)** - モック不要 |
| **Adobe Sign** | 電子署名 | pytest mock / 未設定でも起動可 |
| **OpenAI API** | LLM チャット、Embedding | **必須: APIキー取得が必要** (モックでは意味がない) |
| **Qdrant Cloud** | ベクトル検索 | ローカル Qdrant Docker or `qdrant/qdrant` イメージ |
| **Firestore** | チャット履歴 | Firestore エミュレータ (`firebase emulators`) |
| **GCP Document AI** | OCR (高精度) | Tesseract フォールバックあり、任意 |
| **Keycloak** | SSO/SAML | **Docker Compose に含まれる** - モック不要 |
| **Firebase** | フロント認証設定 | 任意、未設定でも起動可 |
| **Langfuse** | LLM オブザーバビリティ | 任意、未設定でも起動可 |
| **TinyMCE** | フロント WYSIWYG | 任意、未設定でも起動可 |

---

## 5. 開発環境セットアップ手順

### 5.1 前提条件

- [ ] Docker / Docker Compose がインストールされている
- [ ] Python 3.8 (conpass-backend) / Python 3.12 (conpass-agent-backend)
- [ ] Pipenv がインストールされている (`pip install pipenv`)
- [ ] uv がインストールされている (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] Node.js (フロントエンドビルド用、必要に応じて)

### 5.2 conpass-backend セットアップ

```bash
cd conpass-backend

# 1. 環境変数ファイルを作成
cp .env.example .env
# .env を編集して必要な API キーを設定

# 2. Docker Compose でサービス起動
docker-compose up -d

# 3. DB マイグレーション（初回のみ）
docker-compose exec app pipenv run python app/manage.py migrate

# 4. 管理ユーザー作成（初回のみ）
docker-compose exec app pipenv run python app/manage.py createsuperuser

# 5. 動作確認
curl http://localhost:8800/api/  # Nginx 経由
```

### 5.3 conpass-agent-backend セットアップ

```bash
cd conpass-agent-backend

# 1. 環境変数ファイルを作成
cp .env.example .env
# .env を編集 (OPENAI_API_KEY, QDRANT_URL 等を設定)

# 2. 依存パッケージインストール
uv sync

# 3. ローカル起動
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# 4. 動作確認
curl http://localhost:8080/health
curl http://localhost:8080/docs  # Swagger UI
```

### 5.4 テスト実行

```bash
# conpass-backend
cd conpass-backend
pipenv run pytest tests/ --showlocals --cov-report=html:htmlcov --cov=app

# Lint
pipenv run lint
```

---

## 6. 最低限動かすために必要なもの (MVP)

### conpass-backend のみ動かす場合

1. Docker Compose で全サービスを起動 (`docker-compose up`)
2. `.env` は `.env.example` をコピーするだけでDB/Redis/MailDevは動作
3. GCP/Azure/AdobeSign の API キーがなくても基本 CRUD 操作は可能
4. GCS 関連機能（ファイルアップロード等）を使う場合は GCP サービスアカウントキーが必要

### conpass-agent-backend も動かす場合

上記に加えて:

1. **OpenAI API キー** (必須 - LLM/Embedding に利用)
2. **Qdrant** (必須 - ベクトル検索)
   - クラウド: Qdrant Cloud のアカウント作成 + API キー取得
   - ローカル: `docker run -p 6333:6333 qdrant/qdrant`
3. **Firestore** (必須 - チャット履歴)
   - ローカル: Firebase エミュレータで代用可能
4. **Redis** (必須) - conpass-backend の Docker Compose に含まれる (8803)
5. `CONPASS_JWT_SECRET` を conpass-backend と合わせる

---

## 7. ポートマップ (全体)

| ポート | サービス | リポジトリ |
|---|---|---|
| 1717 | Django app (uWSGI 直接) | conpass-backend |
| 1718 | Django worker2 (uWSGI 直接) | conpass-backend |
| 8800 | Nginx (フロントプロキシ) | conpass-backend |
| 8802 | MySQL | conpass-backend |
| 8803 | Redis | conpass-backend |
| 8804 | MailDev Web UI | conpass-backend |
| 8805 | MailDev SendGrid API | conpass-backend |
| 8806 | Celery Worker エンドポイント | conpass-backend |
| 18080 | Keycloak 管理画面 | conpass-backend |
| 8080 | Agent Backend (FastAPI) | conpass-agent-backend |
