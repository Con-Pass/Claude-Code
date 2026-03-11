import datetime
from dateutil.relativedelta import relativedelta

import pytest
from django.test import TestCase
from rest_framework.test import override_settings
from rest_framework.test import APIClient
from rest_framework_jwt.serializers import jwt_payload_handler
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_encode_handler

from conpass.models import Contract, Directory, User, MetaKey
from conpass.models.constants.contractmetakeyidable import ContractMetaKeyIdable
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.tests.factories.account import AccountFactory
from conpass.tests.factories.contract import ContractFactory
from conpass.tests.factories.directory_permission import DirectoryPermissionFactory
from conpass.tests.factories.meta_data import MetaDataFactory
from conpass.tests.factories.meta_key import MetaKeyFactory


class TestPaginateView:
    def _modify_directory_viewable(self, contracts: [Contract], login_user: User):
        # 作った契約書が見られるように、階層の設定を行う
        for contract in contracts:
            attributes = {
                'user': login_user,
                'directory': contract.directory,
            }
            DirectoryPermissionFactory.create(**attributes)

    @pytest.mark.django_db
    @override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
    def test__sys_401(self, sys_client):
        response = sys_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value
        })

        assert 401 == response.status_code

    @pytest.mark.django_db
    @override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
    def test_get__paginate_10(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contracts = ContractFactory.create_batch(10, **attributes)
        self._modify_directory_viewable(contracts, login_user)

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value
        })
        assert 200 == response.status_code, response.data
        assert 10 == len(response.data['results'])
        assert 10 == response.data['page_total']
        assert 1 == response.data['page_number']
        assert 1 == response.data['page_count']

    @pytest.mark.django_db
    @override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
    def test_get__paginate_11__page1(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contracts = ContractFactory.create_batch(11, **attributes)
        self._modify_directory_viewable(contracts, login_user)

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value
        })

        assert 200 == response.status_code, response.data
        assert 10 == len(response.data['results'])
        assert 11 == response.data['page_total']
        assert 1 == response.data['page_number']
        assert 2 == response.data['page_count']

    @pytest.mark.django_db
    @override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
    def test_get__paginate_11__page2(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contracts = ContractFactory.create_batch(11, **attributes)
        self._modify_directory_viewable(contracts, login_user)

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value,
            'page': 2,
        })

        assert 200 == response.status_code, response.data
        assert 1 == len(response.data['results'])
        assert 11 == response.data['page_total']
        assert 2 == response.data['page_number']
        assert 2 == response.data['page_count']

    @pytest.mark.django_db
    @override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
    def test_get__paginate_11__page3(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contracts = ContractFactory.create_batch(11, **attributes)
        self._modify_directory_viewable(contracts, login_user)

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value,
            'page': 3,
        })

        assert 404 == response.status_code, response.data
        assert '不正なページです。' == response.data['detail']

    @pytest.mark.django_db
    def test_get__meta_data(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contract: Contract = ContractFactory.create(**attributes)
        self._modify_directory_viewable([contract], login_user)

        MetaDataFactory.create(
            contract=contract,
            date_value=datetime.date(2000, 1, 1),
            key=(MetaKeyFactory.create(label='contractenddate')),
        )
        MetaDataFactory.create(
            contract=contract,
            date_value=datetime.date(2000, 2, 1),
            key=(MetaKeyFactory.create(label='cancelnotice')),
        )

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value,
        })

        assert 200 == response.status_code, response.data
        assert '2000-01-01' == response.data['results'][0]['endDate']
        assert '2000-02-01' == response.data['results'][0]['noticeDate']

    @pytest.mark.django_db
    def test_get__フォルダの表示可否(self, api_client, login_user):
        attributes = {
            'account': login_user.account,
            'type': Contract.ContractType.TEMPLATE.value,
        }
        contracts: Contract = ContractFactory.create_batch(2, **attributes)
        self._modify_directory_viewable(contracts[0:1], login_user)

        response = api_client.get('/api/contract/paginate', {
            'type': Contract.ContractType.TEMPLATE.value,
        })

        assert 200 == response.status_code, response.data
        assert 1 == len(response.data['results']), ""
        assert contracts[0].id == response.data['results'][0]['id']


@override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
class TestContractRelated(TestCase):
    def setUp(self):
        account = AccountFactory()
        self.login_user = User.objects.create_user(
            login_name='unittest@example.com',
            password='secret',
            type=User.Type.ACCOUNT.value,
            account=account
        )

        self.api_client = APIClient()
        self.api_client.login(login_name=self.login_user.login_name, password=self.login_user.password)
        payload = jwt_payload_handler(self.login_user)
        token = jwt_encode_handler(payload)
        self.api_client.cookies[api_settings.JWT_AUTH_COOKIE] = token

        attributes_1 = {
            'name': 'contract_1',
            'account': self.login_user.account,
            'type': Contract.ContractType.CONTRACT.value,
        }
        self.contract_1: Contract = ContractFactory.create(**attributes_1)
        attributes = {
            'user': self.login_user,
            'directory': self.contract_1.directory,
        }
        DirectoryPermissionFactory.create(**attributes)

    def test_related_contracts_list(self):
        for i in range(15):
            attributes_1 = {
                'name': f'contract_{i}',
                'account': self.login_user.account,
                'type': Contract.ContractType.CONTRACT.value,
            }
            related_contract = ContractFactory.create(**attributes_1)
            attributes = {
                'user': self.login_user,
                'directory': related_contract.directory,
            }
            DirectoryPermissionFactory.create(**attributes)
            self.contract_1.related_contracts.add(related_contract)
        self.contract_1.save()
        response = self.api_client.get(f'/api/contract/related/{self.contract_1.id}/', {
            'page': 1
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 10
        assert response.data['page_total'] == 15

        response = self.api_client.get(f'/api/contract/related/{self.contract_1.id}/', {
            'page': 2
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 5
        assert response.data['page_total'] == 15

    def test_related_contracts_post_add(self):
        attributes_1 = {
            'name': 'contract_2',
            'account': self.login_user.account,
            'type': Contract.ContractType.CONTRACT.value,
        }
        contract_2 = ContractFactory.create(**attributes_1)

        response = self.api_client.post(f'/api/contract/related/{self.contract_1.id}/', {
            'related_contract_id': contract_2.id,
            'action': 'add'
        })
        assert response.status_code == 200
        assert response.data['name'] == contract_2.name
        assert self.contract_1.related_contracts.all().count() == 1

    def test_related_contracts_post_remove(self):
        attributes_1 = {
            'name': 'contract_2',
            'account': self.login_user.account,
            'type': Contract.ContractType.CONTRACT.value,
        }
        contract_2 = ContractFactory.create(**attributes_1)
        self.contract_1.related_contracts.add(contract_2)
        self.contract_1.save()
        contract_2.related_contracts.add(self.contract_1)
        contract_2.save()

        response = self.api_client.post(f'/api/contract/related/{self.contract_1.id}/', {
            'related_contract_id': contract_2.id,
            'action': 'remove'
        })
        assert response.status_code == 200
        assert response.data['name'] == contract_2.name
        assert self.contract_1.related_contracts.all().count() == 0

    def test_related_contracts_post_error(self):
        attributes_1 = {
            'name': 'contract_2',
            'account': self.login_user.account,
            'type': Contract.ContractType.CONTRACT.value,
        }
        contract_2 = ContractFactory.create(**attributes_1)

        response = self.api_client.post(f'/api/contract/related/{self.contract_1.id}/', {
            'action': 'add'
        })
        assert response.status_code == 400
        assert response.data['error'] == 'リクエストが間違っている'

        response = self.api_client.post(f'/api/contract/related/{self.contract_1.id}/', {
            'related_contract_id': contract_2.id,
        })
        assert response.status_code == 400
        assert response.data['error'] == 'リクエストが間違っている'

        response = self.api_client.post(f'/api/contract/related/{self.contract_1.id}/', {
            'related_contract_id': contract_2.id,
            'action': 'test_action'
        })
        assert response.status_code == 400
        assert response.data['error'] == '無効なアクション'

    def test_account_contracts_list(self):
        for i in range(15):
            attributes_1 = {
                'name': f'contract_{i}',
                'account': self.login_user.account,
                'type': Contract.ContractType.CONTRACT.value,
                'directory__status': True
            }
            contract = ContractFactory.create(**attributes_1)
            attributes = {
                'user': self.login_user,
                'directory': contract.directory,
            }
            DirectoryPermissionFactory.create(**attributes)
        response = self.api_client.get(f'/api/contract/account/{self.contract_1.id}/', {
            'page': 1
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 10
        assert response.data['page_total'] == 15

        response = self.api_client.get(f'/api/contract/account/{self.contract_1.id}/', {
            'page': 2
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 5
        assert response.data['page_total'] == 15

        response = self.api_client.get(f'/api/contract/account/{self.contract_1.id}/', {
            'page': 1,
            'search_term': 'contract_14'
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['page_total'] == 1


@override_settings(REST_FRAMEWORK={'PAGE_SIZE': 10})
class TestContractWithMetaList(TestCase):
    def setUp(self):
        account = AccountFactory()
        self.user = User.objects.create_user(
            login_name='unittest@example.com',
            password='secret',
            type=User.Type.ACCOUNT.value,
            account=account
        )
        self.api_client = APIClient()
        self.api_client.login(login_name=self.user.login_name, password=self.user.password)
        payload = jwt_payload_handler(self.user)
        token = jwt_encode_handler(payload)
        self.api_client.cookies[api_settings.JWT_AUTH_COOKIE] = token

        # MetaKey作成
        self.contract_end_date_meta_key = MetaKeyFactory.create(
            id=ContractMetaKeyIdable.MetaKeyId.CONTRACTENDDATE.value,
            label='contractenddate')
        self.auto_update_meta_key = MetaKeyFactory.create(
            id=ContractMetaKeyIdable.MetaKeyId.AUTOUPDATE.value,
            label='autoupdate')
        self.cancel_notice_meta_key = MetaKeyFactory.create(
            id=ContractMetaKeyIdable.MetaKeyId.CONPASS_CONTRACT_RENEW_NOTIFY.value,
            label='conpass_contract_renew_notify')
        self.conpass_person_key = MetaKeyFactory.create(
            id=ContractMetaKeyIdable.MetaKeyId.CONPASS_PERSON.value,
            label='conpass_person')

        attributes = {
            'account': self.user.account,
            'type': Contract.ContractType.CONTRACT.value,
            'status': ContractStatusable.Status.SIGNED.value,
        }
        contracts = ContractFactory.create_batch(30, **attributes)
        for contract in contracts:
            attributes = {
                'user': self.user,
                'directory': contract.directory,
            }
            DirectoryPermissionFactory.create(**attributes)
            # メタデータ作成
            # 契約終了日
            MetaDataFactory.create(
                contract=contract,
                date_value=datetime.datetime.now() + datetime.timedelta(days=10),
                key=self.contract_end_date_meta_key,
            )
            # 契約更新通知対象
            MetaDataFactory.create(
                contract=contract,
                value=1,
                key=self.cancel_notice_meta_key,
            )
            # 自動更新なし
            MetaDataFactory.create(
                contract=contract,
                value=0,
                key=self.auto_update_meta_key,
            )
            # 担当者
            MetaDataFactory.create(
                contract=contract,
                value=self.user.id,
                key=self.conpass_person_key,
            )

    def test_cancel_notice_contract_all(self):
        response = self.api_client.get('/api/contract/data/meta/list', {
            'page': 1
        })
        assert response.status_code == 200
        assert len(response.data['results']) == 10
        assert response.data['page_count'] == 3

    def test_no_cancel_notice_contract(self):
        # Cancel notice set to 0
        contract = ContractFactory(
            account=self.user.account,
            type=Contract.ContractType.CONTRACT.value,
            status=ContractStatusable.Status.SIGNED.value,
        )
        DirectoryPermissionFactory.create(user=self.user, directory=contract.directory)
        MetaDataFactory.create(
            contract=contract,
            value=0,
            key=self.cancel_notice_meta_key
        )
        response = self.api_client.get('/api/contract/data/meta/list', {
            'page': 1
        })
        assert response.status_code == 200
        assert contract.id not in [result['id'] for result in response.data['results']]

    def test_contract_end_date_before_created_at(self):
        # End date before creation date
        contract = ContractFactory(
            account=self.user.account,
            type=Contract.ContractType.CONTRACT.value,
            status=ContractStatusable.Status.SIGNED.value,
        )
        DirectoryPermissionFactory.create(user=self.user, directory=contract.directory)
        MetaDataFactory.create(
            contract=contract,
            date_value=contract.created_at - datetime.timedelta(days=1),
            key=self.contract_end_date_meta_key
        )
        response = self.api_client.get('/api/contract/data/meta/list', {
            'page': 1
        })
        assert response.status_code == 200
        assert contract.id not in [result['id'] for result in response.data['results']]

    def test_contract_end_date_sorted(self):
        # Create contracts with different end dates
        end_dates = [datetime.datetime.now() + datetime.timedelta(days=i) for i in range(3)]
        contracts = []
        for i in range(3):
            contract = ContractFactory(
                account=self.user.account,
                type=Contract.ContractType.CONTRACT.value,
                status=ContractStatusable.Status.SIGNED.value,
            )
            DirectoryPermissionFactory.create(user=self.user, directory=contract.directory)
            MetaDataFactory.create(
                contract=contract,
                date_value=end_dates[i],
                key=self.contract_end_date_meta_key
            )
            contracts.append(contract)
        response = self.api_client.get('/api/contract/data/meta/list', {
            'page': 1
        })
        assert response.status_code == 200
        sorted_results = sorted(response.data['results'], key=lambda x: x['meta_data'][self.contract_end_date_meta_key.name])
        assert [result['id'] for result in response.data['results']] == [result['id'] for result in sorted_results]

    def test_contract_end_date_within_a_month(self):
        # End date more than a month from now
        contract = ContractFactory(
            account=self.user.account,
            type=Contract.ContractType.CONTRACT.value,
            status=ContractStatusable.Status.SIGNED.value,
        )
        DirectoryPermissionFactory.create(user=self.user, directory=contract.directory)
        MetaDataFactory.create(
            contract=contract,
            date_value=datetime.datetime.now() + relativedelta(months=1, days=1),
            key=self.contract_end_date_meta_key
        )
        response = self.api_client.get('/api/contract/data/meta/list', {
            'page': 1
        })
        assert response.status_code == 200
        assert contract.id not in [result['id'] for result in response.data['results']]
