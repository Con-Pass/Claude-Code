# ConPass フロントエンド UI 実装タスク

## 完了済み
- [x] Docker環境起動（conpass-backend: 8800, conpass-agent-backend）
- [x] DBマイグレーション完了（78 + Playbook 0079）
- [x] adminユーザー作成（admin / admin1234）
- [x] サンプル契約書10件作成（3アカウント×複数件）
- [x] テスト実行（33件 全PASSED）
- [x] Vue.js フロントエンド雛形作成（conpass-frontend, port 8801）
- [x] テストユーザー作成（user@example.com / ConPass2024）
- [x] DirectoryPermission 付与（契約書一覧アクセス権）
- [x] Corporate作成・Clientに紐づけ（シリアライザ500エラー解消）
- [x] X-Frontend-Env: local ヘッダーでcookie認証動作確認
- [x] 契約書API（/api/contract/paginate?type=1）→ 4件正常返却

## 現在の状態
- Viteサーバー: http://localhost:8801/ (起動中)
- API: http://localhost:8800/api/ (稼働中)
- ログイン情報: user@example.com / ConPass2024

## フロントエンド画面
| 画面 | パス |
|------|------|
| ログイン | /login |
| ダッシュボード | /dashboard |
| 契約書一覧 | /contracts |
| Playbook管理 | /playbooks |
