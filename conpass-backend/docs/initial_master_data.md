# 初期マスタデータの投入方法

他のダミー、サンプルデータと違い、実際に必要になるマスタデータとなります。  

[ダミーデータ](initial_dummy_data.md)より先に投入してください


- workflowtaskmaster
  - ワークフローのタスクの種別などのマスタデータ。これを元にタスクを作成する。
  - ワークフローの処理に必要になります。
- permissiontarget
  - ユーザごとの機能権限設定項目のマスタ


## 投入方法
appコンテナに入る
```
docker-compose exec app bash
```

最低限のデータを投入する  
これはダミーデータになりますが、どうしても必要になるので最初に投入します
```
python app/manage.py loaddata app/conpass/fixtures/initialdata.json
```

データ投入を実行する  
```
python app/manage.py loaddata app/conpass/fixtures/metakey.json
python app/manage.py loaddata app/conpass/fixtures/workflowtaskmaster.json
python app/manage.py loaddata app/conpass/fixtures/mail_tag.json
```

