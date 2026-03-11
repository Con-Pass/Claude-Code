# ローカルPoC → pushブランチの完全同期

## ゴール
ローカルPoCディレクトリの現在の状態を **唯一の正** として、
`poc/rag-pipeline-tuning` ブランチをローカルと完全に一致させ、
push権限付与後に `git push` 一発で完了する状態にする。

## 前提
- **正（Source of Truth）**: `/Users/hayashi/Desktop/Claude/ConPass/conpass-agent-backend`
  - 「適法性チェックの改善」セッション等で複数回改善済み。どのファイルが変わったかは不明。
- **pushブランチ**: `/tmp/conpass-agent-backend-main` の `poc/rag-pipeline-tuning`
  - 以前のセッションで2〜3コミット積んだ状態。古い可能性がある。
  - `/tmp/` が消えている場合はリポジトリの再クローンから始めること。
- **conpass-backend** は別リポジトリで既にpush・PR済み。今回の対象外。

---

## Step 1: 環境確認

```bash
SRC=/Users/hayashi/Desktop/Claude/ConPass/conpass-agent-backend
DST=/tmp/conpass-agent-backend-main

# pushブランチが生きているか確認
if [ -d "$DST/.git" ]; then
  cd $DST && git branch -a | grep poc
else
  echo "CLONE_NEEDED"
fi

# ローカルPoCの存在確認
ls $SRC/pyproject.toml
```

- `CLONE_NEEDED` の場合 → Step 1b（再構築）へ
- ブランチが存在する場合 → Step 2へ

### Step 1b: 再構築（/tmp/が消えている場合のみ）
```bash
cd /tmp
git clone git@github.com:ConPass-Nihon-Purple/conpass-agent-backend.git conpass-agent-backend-main
cd conpass-agent-backend-main
git checkout -b poc/rag-pipeline-tuning
```

---

## Step 2: ローカルPoCの変更対象ファイルを特定

PoC関連のディレクトリを網羅的にスキャンし、pushブランチの `main` からの差分と比較する。

```bash
cd $DST
git checkout poc/rag-pipeline-tuning

# A) pushブランチに含まれる全変更ファイル vs ローカルPoC
echo "=== pushブランチのファイル vs ローカルPoC ==="
git diff --name-only main..poc/rag-pipeline-tuning | while read f; do
  if [ -f "$SRC/$f" ]; then
    if diff -q "$SRC/$f" "$DST/$f" > /dev/null 2>&1; then
      echo "IDENTICAL: $f"
    else
      echo "CHANGED:   $f"
    fi
  elif [ -f "$DST/$f" ]; then
    echo "ONLY_IN_PUSH: $f  ← ローカルPoCに存在しない"
  fi
done

# B) ローカルPoCにあってpushブランチのmainにない全ファイル
#    （「適法性チェックの改善」で新規作成された可能性のあるファイル）
echo ""
echo "=== ローカルPoCにのみ存在するファイル（mainと比較）==="
cd $SRC
# PoC関連ディレクトリを網羅
for dir in \
  app/services/chatbot/tools \
  app/services/compliance \
  app/api/v1 \
  app/schemas \
  cloud/cloud_run \
  evaluation \
  scripts \
  app/services/chatbot/tools/law_search \
  app/services/chatbot/tools/law_search/checkpoints; do
  if [ -d "$dir" ]; then
    find "$dir" -type f \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.txt" -o -name "*.toml" \) | while read f; do
      if [ ! -f "$DST/$f" ]; then
        # mainにも存在しないか確認（新規ファイルのみ抽出）
        cd $DST
        if ! git show main:"$f" > /dev/null 2>&1; then
          echo "NEW_IN_LOCAL: $f"
        fi
        cd $SRC
      fi
    done
  fi
done

# C) pyproject.toml, config等の横断ファイルも比較
echo ""
echo "=== 横断ファイルの差分 ==="
for f in pyproject.toml app/config.py app/router.py app/tools.py app/feature_flags.py; do
  if [ -f "$SRC/$f" ] && [ -f "$DST/$f" ]; then
    if ! diff -q "$SRC/$f" "$DST/$f" > /dev/null 2>&1; then
      echo "CHANGED: $f"
    fi
  fi
done
```

---

## Step 3: 差分レポートを作成して私に見せる

Step 2の結果を以下の表形式でまとめて表示してください。
**自動で差し替えを実行しないでください。**

```
| # | ファイル | 状態 | アクション案 | 差分サマリー |
|---|---------|------|------------|-------------|
| 1 | app/services/.../law_search_tool.py | CHANGED | ローカル版で差し替え | 関数Xを追加、Y行変更 |
| 2 | app/services/.../old_file.py | ONLY_IN_PUSH | 削除 | ローカルPoCで不要になった |
| 3 | app/services/.../new_tool.py | NEW_IN_LOCAL | 追加 | 適法性チェック改善で新規作成 |
| 4 | app/config.py | IDENTICAL | 変更なし | — |
```

CHANGEDファイルについては `diff $SRC/$f $DST/$f` の要約（何行変更、主な変更内容）を付記すること。

---

## Step 4: 承認後に差し替え実行

私が表を確認・承認した後に実行：

```bash
cd $DST
git checkout poc/rag-pipeline-tuning

# 1. CHANGEDファイルを差し替え
# 2. ONLY_IN_PUSHファイルを削除（git rm）
# 3. NEW_IN_LOCALファイルを追加（ディレクトリ作成含む）

git add -A
git status  # 最終確認を表示

git commit -m "[PoC] sync: apply compliance check improvements and cleanup

<ここにStep 3の差分サマリーを反映した具体的な変更内容を記載>"
```

---

## Step 5: 最終検証

```bash
cd $DST

# 1. PoC関連ファイルがローカルと完全一致するか検証
echo "=== 残差分チェック ==="
git diff --name-only main..poc/rag-pipeline-tuning | while read f; do
  if [ -f "$SRC/$f" ]; then
    if ! diff -q "$SRC/$f" "$DST/$f" > /dev/null 2>&1; then
      echo "STILL DIFFERENT: $f"
      diff "$SRC/$f" "$DST/$f" | head -5
    fi
  fi
done
# ↑ 出力が空 = 完全同期

# 2. コミットログ
git log --oneline main..poc/rag-pipeline-tuning

# 3. push dry-run
git push origin poc/rag-pipeline-tuning --dry-run
```

dry-runが成功したら「push準備完了」と報告してください。

---

## 重要な注意事項

1. **ローカルPoCが正**。pushブランチ側のファイルが新しく見えても、ローカルPoCに存在しなければ不要ファイルとして扱う
2. **main ブランチにもともと存在するファイル**（PoC以前から存在するファイル）の変更も見逃さないこと。`config.py`、`router.py`、`tools.py`、`pyproject.toml` 等の横断ファイルは特に注意
3. Step 3のレポートを私に見せるまで、ファイルの書き換えは一切しないこと
4. `/tmp/` が消えている場合はStep 1bで再クローンし、ローカルPoCの全PoC関連ファイルを一括コピーしてコミットする（過去のコミット履歴を再現する必要はない。1コミットで良い）
