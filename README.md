# ConPass × Claude Code 共有リポジトリ

別端末でも同じ Claude Code 環境を再現するためのファイル群です。

## ディレクトリ構成

```
├── global/
│   └── CLAUDE.md          # グローバル設定（~/.claude/CLAUDE.md にコピー）
├── conpass/
│   └── CLAUDE.md          # ConPassプロジェクト設定（プロジェクトルートに配置）
└── memory/
    └── MEMORY.md          # Claude の記憶（プロジェクト知識・過去の経緯）
```

## 別端末セットアップ手順

```bash
# 1. このリポジトリをクローン
git clone https://github.com/Con-Pass/Claude-Code.git
cd Claude-Code

# 2. グローバル設定をコピー
mkdir -p ~/.claude
cp global/CLAUDE.md ~/.claude/CLAUDE.md

# 3. ConPassプロジェクト設定をコピー（プロジェクトルートに）
cp conpass/CLAUDE.md /path/to/ConPass/CLAUDE.md
```

Claude Code を起動すると自動的に設定が読み込まれます。

## 更新方法

設定変更時は `git pull` で最新を取得してください。
