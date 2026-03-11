from django.core.management.base import BaseCommand
from dateutil.relativedelta import relativedelta
from django.db.models import Case, When, OuterRef, Subquery, Q, F, Exists, DateField

from conpass.mailer.contract_renew_notice_mailer import SendContractRenewNoticeMailer
from conpass.models import Contract, MetaData, Workflow, User
import datetime

from conpass.models.constants import ContractTypeable
from conpass.models.constants.contractmetakeyidable import ContractMetaKeyIdable
from conpass.models.constants.contractstatusable import ContractStatusable
from conpass.services.directory.directory_service import DirectoryService
from conpass.models.constants.statusable import Statusable


class Command(BaseCommand):
    help = 'Decode the contents of ContractBody and store them in ContractBodySearch and Meilisearch.'

    def handle(self, *args, **kwargs):
        # 対象のContract取得
        # ゴミ箱に入っていない署名済と名称未定
        queryset = (
            Contract.objects
            .filter(
                is_garbage=False,
                status__in=[
                    ContractStatusable.Status.SIGNED.value,
                    ContractStatusable.Status.SIGNED_BY_PAPER.value
                ]
            )
            .prefetch_related('meta_data_contract')
        )
        # 契約終了日と担当者を紐付ける
        # 解約ノーティス日のサブクエリ用フィルタ
        cancel_notice_filter = MetaData.objects.filter(
            key_id=ContractMetaKeyIdable.MetaKeyId.CANCELNOTICE.value,
            contract=OuterRef('pk'),
            date_value__isnull=False
        )
        # 解約ノーティス日のサブクエリ
        cancel_notice_subquery = cancel_notice_filter.order_by('-date_value').values('date_value')[:1]

        # 契約終了日のサブクエリ
        end_date_subquery = MetaData.objects.filter(
            key_id=ContractMetaKeyIdable.MetaKeyId.CONTRACTENDDATE.value,
            contract=OuterRef('id')
        ).order_by('-date_value').values('date_value')[:1]

        # 条件に基づくサブクエリの選択
        queryset = queryset.annotate(
            end_date=Case(
                When(
                    # 解約ノーティス日が存在し、NULLでない場合、その値を使用
                    condition=Exists(cancel_notice_filter),
                    then=Subquery(cancel_notice_subquery, output_field=DateField())
                ),
                # 上記以外の場合、契約終了日を使用
                default=Subquery(end_date_subquery, output_field=DateField())
            )
        )

        # 「契約更新通知」が「通知対象にする」
        queryset = queryset.filter(
            Q(
                meta_data_contract__key_id=ContractMetaKeyIdable.MetaKeyId.CONPASS_CONTRACT_RENEW_NOTIFY.value,
                meta_data_contract__value=1
            )
        )

        # end_date == (現在+1ヶ月) or 現在
        current_date = datetime.date.today()
        one_month_later = current_date + relativedelta(months=1)
        queryset = queryset.filter(
            Q(end_date=one_month_later) | Q(end_date=current_date)
        )
        # 契約終了日 >= アップロード日
        queryset = queryset.filter(Q(end_date__gte=F('created_at')))
        # 重複削除
        queryset = queryset.distinct()

        for contract in queryset:
            try:
                # MetaData
                metadata_objects = contract.meta_data_contract.exclude(status=Statusable.Status.DISABLE.value)
                need_information = [
                    ContractMetaKeyIdable.MetaKeyId.COMPANYA,
                    ContractMetaKeyIdable.MetaKeyId.COMPANYB,
                    ContractMetaKeyIdable.MetaKeyId.TITLE,
                ]
                # date_valueで取得するもの
                need_information_date = [
                    ContractMetaKeyIdable.MetaKeyId.CONTRACTENDDATE,
                    ContractMetaKeyIdable.MetaKeyId.CANCELNOTICE
                ]
                metadata_dict = {key.name.lower(): '' for key in need_information}
                send_user_ids = []
                for metadata in metadata_objects:
                    if metadata.key.id in [key.value for key in need_information]:
                        metadata_dict[metadata.key.label] = metadata.value
                    elif metadata.key.id in [key.value for key in need_information_date]:
                        metadata_dict[metadata.key.label] = metadata.date_value
                    elif metadata.key.id == ContractMetaKeyIdable.MetaKeyId.CONPASS_PERSON.value and metadata.value:
                        send_user_ids.append(int(metadata.value))
                    elif metadata.key.id == ContractMetaKeyIdable.MetaKeyId.AUTOUPDATE.value:
                        if metadata.value == "1":
                            metadata_dict[metadata.key.label] = "あり"
                        elif metadata.value == "0":
                            metadata_dict[metadata.key.label] = "なし"
                # メール送信
                mailer = SendContractRenewNoticeMailer()
                send_users = []
                if send_user_ids:
                    send_users.extend(list(User.objects.filter(pk__in=send_user_ids)))
                # ワークフロー作成者も追加
                workflows = Workflow.objects.filter(contract=contract)
                for workflow in workflows:
                    if workflow.created_by:
                        send_users.append(workflow.created_by)
                # 重複を削除してメール送信
                for user in set(send_users):
                    # 閲覧権限があるもののみ
                    allowed_directories = DirectoryService() \
                        .get_allowed_directories(user, ContractTypeable.ContractType.CONTRACT.value)
                    allowed_directory_ids = [directory.id for directory in allowed_directories]
                    if contract.directory_id in allowed_directory_ids:
                        mailer.send_contract_renew_notice_mail(user, contract.id, metadata_dict)

                        self.stdout.write(
                            self.style.SUCCESS(
                                'Successfully renewal notice'
                                f'user_ids and email {f"user_id:{user.id} email:{user.email}"}'
                                f'contract_id {contract.id}'
                            ))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed renewal notice contract_id {contract.id}. Error: {e}'))
