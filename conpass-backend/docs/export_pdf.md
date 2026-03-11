## PDFエクスポート設定について

[wkhtmltopdf](https://wkhtmltopdf.org/) と、それをラップする [pdfkit](https://github.com/JazzCore/python-pdfkit) を使用しています。

wkhtmltopdf は環境ごとにインストールが必要になります。

また、日本語を使う場合はフォントも必要になります。

### debian（dockerコンテナ）環境

wkhtmltopdf、pdfkit、それにフォントのインストールが Dockerfile および Pipfile に記載されていますので、コンテナの再作成が必要になります。

```
docker-compose build app
docker-compose up -d
```

尚、フォントは [IPAexGothic](https://packages.debian.org/ja/sid/fonts-ipafont-gothic) を使用しています。

### windows環境

[ wkhtmltopdf のダウンロードページ](https://wkhtmltopdf.org/downloads.html)からWindows 用のインストーラをダウンロードし、インストールを実行します。

標準ですと、
```
C:\Program Files\wkhtmltopdf
```
などにインストールされると思います。実行ファイルはその下のbin にあるため、ここにパスを通します。

#### パス設定

1. windowsの設定を開く
2. 「システム」を選択
3. 「詳細情報」を選択
4. 「システムの詳細設定」を選択   
（システムのプロパティが開く）
5. 「詳細設定」タブの「環境変数」を選択
6. ```Path``` を探して選択し、「編集」  
※ユーザー環境変数でもシステム環境変数でもどちらも良いです
7. 「新規」でbinのパス、 
```C:\Program Files\wkhtmltopdf\bin``` を追加
8. 「OK」を押して完了
9. 必要なら IDE の再起動などを行って環境設定の再読み込みを行ってください

尚、windowsの場合、フォントは MSUIGothic など、システムのものが使われるようなので、改めてフォントをインストールする必要はありません。
