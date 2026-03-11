# 初期ダミーデータの投入方法

app/conpass/fixture/*.json に初期ダミーデータがあります。  
特にuserとaccountは何らかデータがないとリレーションの都合で他のデータが処理できないことが多いので、作っておくと良いです。

先に[マスタデータの投入](initial_master_data.md)を行ってください。

## 投入方法
appコンテナに入る
```
docker-compose exec app bash
```

データ投入を実行する  
※この順番で行ってください。
```
python app/manage.py loaddata app/conpass/fixtures/accounts_sample.json
python app/manage.py loaddata app/conpass/fixtures/corporates_sample.json
python app/manage.py loaddata app/conpass/fixtures/users_sample.json
python app/manage.py loaddata app/conpass/fixtures/clients_sample.json
python app/manage.py loaddata app/conpass/fixtures/directories_sample.json
python app/manage.py loaddata app/conpass/fixtures/contracts_sample.json
python app/manage.py loaddata app/conpass/fixtures/metadata_sample.json
```

ダッシュボードの利用要領グラフを表示する場合、以下のコマンドでフェイクデータを投入してください  
過去５ヶ月分のデータを投入します。(今月はリアルタイムの値を使うためデータは作成されません)

```shell
python app/manage.py create_fake_summaries
```

## 注意点
先に既にいくつかデータが作られていたりすると、外部キーがうまく連携できず、投入が出来ない場合があります。  
少なくともプライマリキーが1のデータがあるほうが都合が良いので、問題なければtruncateするなどしてリセットした上で改めてデータ投入をおすすめします。

※外部キーの判定を外す場合は mysql で FOREIGN_KEY_CHECKS = 0 を行います。

dbコンテナに入る
```
docker-compose exec db bash
```

mysqlにログインする
```
mysql -u conpass -p
```

外部キーの判定を外して、truncateする（レコードが全部消えますので注意）  
作業が終わったらまた有効にしておく
```
use conpass

SET FOREIGN_KEY_CHECKS = 0;

truncate table conpass_user;
truncate table conpass_account;
truncate table conpass_corporate;
truncate table conpass_client;
truncate table conpass_contract;
truncate table conpass_contractbody;
truncate table conpass_metadata;
truncate table conpass_metakey;
truncate table conpass_directory;

SET FOREIGN_KEY_CHECKS = 1;
```

（改めてデータ投入をする）
