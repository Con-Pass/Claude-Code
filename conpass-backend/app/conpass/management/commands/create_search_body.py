from django.core.management.base import BaseCommand
from django.conf import settings
import urllib.parse
from django.utils.html import strip_tags
from meilisearch import Client, errors
from conpass.models import ContractBody, ContractBodySearch, Account
from datetime import datetime, timedelta
from django.utils.timezone import make_aware


class Command(BaseCommand):
    help = 'Decode the contents of ContractBody and store them in ContractBodySearch and Meilisearch.'

    def handle(self, *args, **kwargs):
        # ローカルの場合は使用しない
        if settings.RUN_ENV == "local":
            self.stdout.write(self.style.SUCCESS('create_search_body runenv is local'))
            return

        ndate = int(settings.MEILISEARCH_REGISTRATION_PERIOD_FOR_BATCH)
        datetime_now = make_aware(datetime.now())
        past_n_date = datetime_now - timedelta(days=ndate)
        past_n_date_midnight = datetime(past_n_date.year, past_n_date.month, past_n_date.day, 0, 0, 0)
        self.stdout.write(self.style.SUCCESS(f'対象期間: {settings.MEILISEARCH_REGISTRATION_PERIOD_FOR_BATCH}日前 datetime={past_n_date_midnight}'))
        accounts = Account.objects.all()
        self.stdout.write(self.style.SUCCESS(f'対象アカウント数: {len(accounts)}'))

        try:
            # Meilisearchクライアントの設定
            client = Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_API_KEY)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'create_search_body Error connecting to Meilisearch: {e}'))
            return

        # Meilisearchから全データを取得する関数
        def fetch_all_documents(index_name):
            documents = []
            try:
                # インデックスの存在を確認
                client.get_index(index_name)
                index = client.index(index_name)
                page = 0
                hits_per_page = 1000

                while True:
                    results = index.search('', {'offset': page * hits_per_page, 'limit': hits_per_page})
                    documents.extend(results['hits'])
                    if len(results['hits']) < hits_per_page:
                        break
                    page += 1
            except errors.MeilisearchApiError as e:
                # インデックスが存在しない場合は空のリストを返す
                if e.code == 'index_not_found':
                    return documents
                else:
                    raise
            return documents

        # データをインデックスに保存
        def index_contract_body_search(index_name, documents):
            index = client.index(index_name)
            index.add_documents(documents, primary_key='contract_body_id')
            for document in documents:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'create_search_body Successfully saved meilisearch contract_body ID: {document["contract_body_id"]}'
                    )
                )

        # アカウント単位で処理を実行する
        for account in accounts:
            # 対象アカウントのインデックスからデータを取得
            index_name = f"contractbodysearch_{settings.RUN_ENV}_{account.id}"
            existing_documents = fetch_all_documents(index_name)

            # アカウントに紐づくContractBodyを取得する
            wheres = {
                'contract__account__id': account.id,
                'created_at__gte': make_aware(past_n_date_midnight)
            }
            contract_bodies = ContractBody.objects.filter(**wheres).all()
            self.stdout.write(self.style.SUCCESS(f'[アカウントID: {account.id}] 対象contract_body数: {len(contract_bodies)}'))

            documents = []
            bulk_data = []
            for contract_body in contract_bodies:
                contract_body_id = contract_body.id
                # 既にインデックスされている場合、処理をスキップ
                if any(doc['contract_body_id'] == contract_body_id for doc in existing_documents):
                    continue

                try:
                    decoded_body = urllib.parse.unquote(contract_body.body)
                    decoded_body = strip_tags(decoded_body)

                    documents.append({
                        'contract_body_id': contract_body.id,
                        'contract_id': contract_body.contract.id,
                        'search_body': decoded_body
                    })
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"create_search_body Error processing body for contract_body ID: {contract_body_id}. Error: {e}"
                        )
                    )
                    continue

                # 保存されていない場合ContractBodySearchモデルに保存
                # ContractBodySearchでの既存のデータをチェック
                if ContractBodySearch.objects.filter(contract_body=contract_body).exists():
                    self.stdout.write(self.style.WARNING(
                        f"create_search_body ContractBody ID: {contract_body_id} "
                        "is already saved in ContractBodySearch. Skipping."
                    ))
                    continue  # 既にContractBodySearchに保存されている場合、スキップ

                bulk_data.append(ContractBodySearch(
                    contract_body=contract_body,
                    search_body=decoded_body,
                    created_at=datetime_now,
                    created_by=contract_body.created_by,
                    updated_at=datetime_now,
                    updated_by=contract_body.updated_by
                ))

            # インデックスに保存
            if len(documents) != 0:
                # ペイロードにサイズ制限があるため、100件ずつに分割する
                chunk_size = 30
                chunks = [documents[i:i + chunk_size] for i in range(0, len(documents), chunk_size)]
                for document_chunk in chunks:
                    index_contract_body_search(index_name, document_chunk)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'create_search_body Successfully completed saving meilisearch index_name: {index_name} count: {len(documents)}'
                    )
                )

            # MySQLにもBulkで保存
            if len(bulk_data) != 0:
                # ペイロードにサイズ制限があるため、100件ずつに分割する
                chunk_size = 30
                chunks = [bulk_data[i:i + chunk_size] for i in range(0, len(bulk_data), chunk_size)]
                for data_chunk in chunks:
                    ContractBodySearch.objects.bulk_create(data_chunk)

        # インデックスの設定変更
        def update_all_indexes_settings(client):
            offset = 0
            limit = 20

            while True:
                params = {'limit': limit, 'offset': offset}
                response = client.get_indexes(params)
                indexes = response['results']
                if not indexes:
                    break

                for index_obj in indexes:
                    index = client.index(index_obj.uid)
                    index.update_settings({
                        'typoTolerance': {
                            'enabled': False
                        }
                    })

                offset += limit

        update_all_indexes_settings(client)

        self.stdout.write(self.style.SUCCESS('create_search_body Successfully processed contract bodies'))
