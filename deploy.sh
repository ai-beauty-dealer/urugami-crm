#!/bin/bash

# CRM Tool Deployment Script
# 1. データの再解析
# 2. 静的ファイルのビルド/コピー
# 3. GitHubへのプッシュ（オプション）

echo "🚀 CRM Tool のデプロイを開始します..."

# Pythonスクリプトの実行（JSONデータの更新）
echo "📦 データを解析中..."
python3 parse_sales.py

# デプロイ用ディレクトリの準備
DEPLOY_DIR=".deploy"
if [ ! -d "$DEPLOY_DIR" ]; then
    mkdir "$DEPLOY_DIR"
fi

# ファイルのコピー
echo "📋 ファイルをコピー中..."
cp index.html "$DEPLOY_DIR/"
cp salon_products.json "$DEPLOY_DIR/"
cp salon_monthly_sales.json "$DEPLOY_DIR/"

# ローカル確認用のメッセージ
echo "✅ デプロイ準備が完了しました。"
echo "📍 場所: $DEPLOY_DIR"
echo "🌐 ブラウザで index.html を開いて動作確認してください。"

# GitHubへのプッシュ（自動）
git add .
git commit -m "Auto-deploy: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main
echo "🚀 GitHubに同期完了しました。"
