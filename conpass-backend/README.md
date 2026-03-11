[![CI](https://github.com/ultinet-inc/conpass/actions/workflows/ci.yml/badge.svg)](https://github.com/ultinet-inc/conpass/actions/workflows/ci.yml)

# conpass
日本パープル　電子契約システム

## 最初によむもの
- [Docker 開発環境](docs/docker_environment.md)
- ブランチ運用について(TODO)
- 初期データの投入
  - [初期マスタデータの投入方法](docs/initial_master_data.md)
  - [初期ダミーデータの投入方法](docs/initial_dummy_data.md)
- [エディタ・IDE設定について](docs/tools.md)
- [PDFエクスポート設定について](docs/export_pdf.md)
- [GCP の初期設定](docs/gcp_setting.md)
- [GCP への**手動**デプロイ手順](docs/gcp_deploy_manually.md)


## 使用ポート一覧

| PORT | 用途                                    | 
|------|---------------------------------------|
| 8800 | webコンテナ. docker環境のフロントエンドポート          | 
| 8801 | ローカル vue cliサーバ. pycharm環境のフロントエンドポート |
| 8802 | db コンテナ                               |
| 8803 | redisコンテナ                             |
| 8804 | maildevコンテナ. メールをブラウザで確認できるエンドポイント    |
| 8805 | maildevコンテナ. APIサーバ                   |
| 8806 | workerコンテナ.celery jobの投入エンドポイント       |
| 8811 | pycharm環境のバックエンドポート                   |
