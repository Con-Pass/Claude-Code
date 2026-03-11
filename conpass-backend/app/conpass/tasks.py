import time
import threading
from logging import getLogger
from typing import Union

from celery import shared_task

from django.conf import settings

from conpass.services.contract.contract_service import ContractService
from conpass.services.azure.azure_prediction import AzurePredict, PredictionRequestFile
from conpass.services.growth_verse.gv_prediction import GvPredict, GvPredictionRequestFile
from conpass.services.gcp.vision import GoogleCloudVision

from common.utils.http_utils import execute_http_post

logger = getLogger('celery')


@shared_task
def add(x, y):

    def execute(val1, val2):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/add'
            data = {'x': val1, 'y': val2}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"add execute request error: {e}")

    thread = threading.Thread(target=execute, args=(x, y))
    thread.start()
    return True


def add_execute(x, y):
    logger.info('処理中')
    logger.info(__name__)
    z = x + y
    time.sleep(10)
    logger.info('hello')
    logger.info('処理完了')
    return z


@shared_task
def vision_scan_pdf_task(filename: str, contractId: int, userId: int):
    """
    GoogleCloudVisionを使って、PDFファイルの本文を（画像として）スキャンし、テキスト化する
    """
    logger.info("vison scan start:" + filename)
    logger.info(__name__)

    def execute(fname, cid, uid):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/vision-scan-pdf-task'
            data = {'filename': fname, 'contractId': cid, 'userId': uid}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"vision_scan_pdf_task execute request error: {e}")

    thread = threading.Thread(target=execute, args=(filename, contractId, userId))
    thread.start()
    return True


def vision_scan_pdf_task_execute(filename: str, contractId: int, userId: int):
    """
    GoogleCloudVisionを使って、PDFファイルの本文を（画像として）スキャンし、テキスト化する
    """
    logger.info("vison scan start:" + filename)
    logger.info(__name__)
    try:
        vision = GoogleCloudVision()
        result = vision.scan_pdf(filename)
        # 読み取った本文を登録する
        # result は配列なので、改行で連結する
        contract_service = ContractService
        contract_service.save_body(contractId, "\\n".join(result), 1, userId)
    except Exception as e:
        logger.error(e)
        raise e

    logger.info(result)
    return result


@shared_task
def prediction_task(file: Union[PredictionRequestFile, GvPredictionRequestFile]):
    """
    GoogleCloudPredictionを使って、PDFファイルの本文からメタ情報を抽出します
    """
    logger.info("prediction start:" + file.url)
    logger.info(__name__)

    def execute(f: Union[PredictionRequestFile, GvPredictionRequestFile]):
        try:
            url = settings.PRIVATE_API_URL + '/private/task/execute/prediction-task'
            data = {'id': f.id, 'url': f.url}
            execute_http_post(url, data)
        except Exception as e:
            logger.error(f"prediction_task execute request error: {e}")

    thread = threading.Thread(target=execute, args=(file,))
    thread.start()
    return True


def prediction_task_execute(file: Union[PredictionRequestFile, GvPredictionRequestFile]):
    """
    GoogleCloudPredictionを使って、PDFファイルの本文からメタ情報を抽出します
    """
    logger.info("prediction start:" + file.url)
    logger.info(__name__)
    try:
        files = [file]
        if settings.GV_ENTITY_EXTRACTION_GPT_ENDPOINT:
            predict = GvPredict()
            results = predict.get_predict(gcs_files=files, conpass_contract_type="その他")
        else:
            predict = AzurePredict()
            results = predict.get_predict(gcs_files=files)

    except Exception as e:
        logger.error(e)
        raise e

    logger.info(results)
    return results


# ============================================================
# コンプライアンスアラート関連タスク
# ============================================================

@shared_task
def evaluate_tenant_rules_for_account(account_id: int):
    """
    指定アカウントの全TenantRuleを全Contract対して評価する。
    WARN/FAILの評価結果があればRuleEvaluationLogに記録し、
    重要度に応じてアラートメール送信タスクをキューに投入する。
    """
    from conpass.models import Account, Contract
    from conpass.models.playbook import TenantRuleSet, TenantRule, RuleEvaluationLog

    logger.info(f"evaluate_tenant_rules_for_account start: account_id={account_id}")

    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        logger.error(f"Account not found: {account_id}")
        return False

    # アカウントに紐づくアクティブなルールセットを取得
    rule_sets = TenantRuleSet.objects.filter(
        account=account, is_active=True
    ).prefetch_related('rules')

    # アカウントに紐づく有効な契約を取得
    contracts = Contract.objects.filter(
        account=account, status=1
    )

    evaluated_count = 0
    alert_count = 0

    for rule_set in rule_sets:
        active_rules = rule_set.rules.filter(is_active=True)

        for rule in active_rules:
            for contract in contracts:
                result = _evaluate_single_rule(rule, contract)

                if result in ('WARN', 'FAIL'):
                    log = RuleEvaluationLog.objects.create(
                        rule=rule,
                        contract=contract,
                        result=result,
                        detail={
                            'rule_type': rule.rule_type,
                            'condition': rule.condition,
                            'severity': rule.severity,
                        },
                    )
                    evaluated_count += 1

                    # CRITICAL は即時メール送信
                    if rule.severity == 'CRITICAL':
                        send_compliance_alert_email.delay(log.id)
                        alert_count += 1

    logger.info(
        f"evaluate_tenant_rules_for_account done: account_id={account_id}, "
        f"evaluated={evaluated_count}, alerts_sent={alert_count}"
    )
    return True


def _evaluate_single_rule(rule, contract):
    """
    単一ルールを単一契約に対して評価する。
    返却値: 'PASS', 'WARN', 'FAIL'
    """
    from django.utils import timezone
    from conpass.models import MetaData

    try:
        rule_type = rule.rule_type
        condition = rule.condition or {}

        if rule_type == 'EXPIRY_ALERT':
            # 期限アラート: contractenddate が条件日数以内かチェック
            days_before = condition.get('days_before', 90)
            end_date_meta = MetaData.objects.filter(
                contract=contract, meta_key__name='contractenddate'
            ).first()
            if end_date_meta and end_date_meta.value:
                from datetime import datetime, timedelta
                try:
                    end_date = datetime.strptime(str(end_date_meta.value), '%Y-%m-%d').date()
                    threshold = timezone.now().date() + timedelta(days=days_before)
                    if end_date <= timezone.now().date():
                        return 'FAIL'
                    elif end_date <= threshold:
                        return 'WARN'
                except (ValueError, TypeError):
                    pass
            return 'PASS'

        elif rule_type == 'AMOUNT_THRESHOLD':
            # 金額閾値: 契約金額が閾値を超えていないかチェック
            max_amount = condition.get('max_amount')
            if max_amount is not None:
                amount_meta = MetaData.objects.filter(
                    contract=contract, meta_key__name='amount'
                ).first()
                if amount_meta and amount_meta.value:
                    try:
                        amount = float(str(amount_meta.value).replace(',', ''))
                        if amount > float(max_amount):
                            return 'FAIL' if rule.severity == 'CRITICAL' else 'WARN'
                    except (ValueError, TypeError):
                        pass
            return 'PASS'

        elif rule_type == 'REQUIRED_CONTRACT':
            # 必須契約種別: 特定の契約種別が存在するかチェック（パス判定のみ）
            return 'PASS'

        elif rule_type == 'BENCHMARK_DEVIATION':
            # ベンチマーク逸脱: 将来的にBenchmarkServiceと連携
            return 'PASS'

        elif rule_type == 'LAW_UPDATE':
            # 法令改正: 将来的に法令規制基盤と連携
            return 'PASS'

        elif rule_type == 'CUSTOM_AI':
            # AIカスタム評価: 将来的にLLM評価と連携
            return 'PASS'

        else:
            logger.warning(f"Unknown rule_type: {rule_type}")
            return 'PASS'

    except Exception as e:
        logger.error(f"Rule evaluation error: rule={rule.id}, contract={contract.id}, error={e}")
        return 'PASS'


@shared_task
def send_compliance_alert_email(evaluation_log_id: int):
    """
    RuleEvaluationLog(WARN/FAIL)をトリガーにアラートメールを送信する。
    severity == CRITICAL → 即時送信
    severity == WARNING → 日次バッチで集約（このタスクでは即時送信もサポート）
    """
    from conpass.models.playbook import RuleEvaluationLog
    from conpass.models import User
    from conpass.mailer.compliance_alert_mailer import ComplianceAlertMailer

    logger.info(f"send_compliance_alert_email start: log_id={evaluation_log_id}")

    try:
        log = RuleEvaluationLog.objects.select_related(
            'rule', 'rule__rule_set', 'rule__rule_set__account', 'contract'
        ).get(id=evaluation_log_id)
    except RuleEvaluationLog.DoesNotExist:
        logger.error(f"RuleEvaluationLog not found: {evaluation_log_id}")
        return False

    rule = log.rule
    contract = log.contract
    account = rule.rule_set.account

    # アカウントの管理者ユーザーを取得してメール送信
    admin_users = User.objects.filter(
        account=account, status=1
    ).exclude(email='').exclude(email__isnull=True)

    if not admin_users.exists():
        logger.warning(f"No admin users found for account {account.id}")
        return False

    mailer = ComplianceAlertMailer()
    detail_text = _format_evaluation_detail(log.detail)
    recommended_action = _get_recommended_action(rule.rule_type, log.result)

    for user in admin_users:
        try:
            mailer.send_compliance_alert_mail(
                user=user,
                rule_name=rule.name,
                rule_severity=rule.severity,
                contract_id=contract.id,
                contract_name=contract.name,
                result=log.result,
                detail=detail_text,
                recommended_action=recommended_action,
            )
        except Exception as e:
            logger.error(
                f"Failed to send compliance alert to {user.email}: {e}"
            )

    logger.info(f"send_compliance_alert_email done: log_id={evaluation_log_id}")
    return True


@shared_task
def daily_compliance_summary_email(account_id: int):
    """
    毎日朝8時: 未対応WARN/FAILアラートの日次サマリーメールを送信する。
    前日分のRuleEvaluationLog(WARN/FAIL)を集計してサマリーメールとする。
    """
    from django.utils import timezone
    from datetime import timedelta
    from conpass.models import Account, User
    from conpass.models.playbook import RuleEvaluationLog
    from conpass.mailer.compliance_alert_mailer import ComplianceAlertMailer

    logger.info(f"daily_compliance_summary_email start: account_id={account_id}")

    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        logger.error(f"Account not found: {account_id}")
        return False

    # 過去24時間のWARN/FAILログを取得
    since = timezone.now() - timedelta(hours=24)
    logs = RuleEvaluationLog.objects.filter(
        rule__rule_set__account=account,
        result__in=['WARN', 'FAIL'],
        evaluated_at__gte=since,
    ).select_related('rule', 'contract')

    if not logs.exists():
        logger.info(f"No compliance alerts for account {account_id} in last 24h")
        return True

    warn_count = logs.filter(result='WARN').count()
    fail_count = logs.filter(result='FAIL').count()

    # 緊急アイテムのリストを作成
    critical_items = []
    for log in logs.filter(rule__severity='CRITICAL'):
        critical_items.append({
            'rule_name': log.rule.name,
            'contract_id': log.contract.id,
            'contract_name': log.contract.name,
            'result': log.get_result_display(),
        })

    summary_date = timezone.now().strftime('%Y-%m-%d')

    # アカウントのユーザーにサマリーメールを送信
    admin_users = User.objects.filter(
        account=account, status=1
    ).exclude(email='').exclude(email__isnull=True)

    mailer = ComplianceAlertMailer()
    for user in admin_users:
        try:
            mailer.send_daily_summary_mail(
                user=user,
                total_warn_count=warn_count,
                total_fail_count=fail_count,
                critical_items=critical_items,
                summary_date=summary_date,
            )
        except Exception as e:
            logger.error(
                f"Failed to send daily summary to {user.email}: {e}"
            )

    logger.info(
        f"daily_compliance_summary_email done: account_id={account_id}, "
        f"warn={warn_count}, fail={fail_count}"
    )
    return True


@shared_task
def daily_compliance_summary_all_accounts():
    """
    全アクティブアカウントに対して日次コンプライアンスサマリーを送信する。
    Celery Beatから毎日AM8:00にスケジュール実行される。
    """
    from conpass.models import Account

    logger.info("daily_compliance_summary_all_accounts start")

    active_accounts = Account.objects.filter(status=Account.Status.ENABLE.value)
    count = 0

    for account in active_accounts:
        daily_compliance_summary_email.delay(account.id)
        count += 1

    logger.info(f"daily_compliance_summary_all_accounts: queued {count} accounts")
    return True


def _format_evaluation_detail(detail: dict) -> str:
    """評価詳細を読みやすいテキストに整形する"""
    if not detail:
        return "詳細情報なし"

    parts = []
    if detail.get('rule_type'):
        rule_type_display = {
            'EXPIRY_ALERT': '期限アラート',
            'REQUIRED_CONTRACT': '必須契約種別',
            'AMOUNT_THRESHOLD': '金額閾値',
            'BENCHMARK_DEVIATION': 'ベンチマーク逸脱',
            'LAW_UPDATE': '法令改正',
            'CUSTOM_AI': 'AIカスタム評価',
        }.get(detail['rule_type'], detail['rule_type'])
        parts.append(f"ルール種別: {rule_type_display}")

    if detail.get('condition'):
        parts.append(f"条件: {detail['condition']}")

    return '\n'.join(parts) if parts else "詳細情報なし"


def _get_recommended_action(rule_type: str, result: str) -> str:
    """ルール種別と結果に基づいて推奨アクションを返す"""
    actions = {
        'EXPIRY_ALERT': {
            'WARN': '契約終了日が近づいています。更新・解約の判断をご検討ください。',
            'FAIL': '契約が期限切れです。至急、更新または後続対応をご確認ください。',
        },
        'AMOUNT_THRESHOLD': {
            'WARN': '契約金額が設定閾値を超えています。上長承認の確認をお願いします。',
            'FAIL': '契約金額が設定閾値を大幅に超えています。至急ご確認ください。',
        },
        'BENCHMARK_DEVIATION': {
            'WARN': '業界ベンチマークからの逸脱が検出されました。契約条件の見直しをご検討ください。',
            'FAIL': '業界ベンチマークから大幅に逸脱しています。至急ご確認ください。',
        },
    }
    return actions.get(rule_type, {}).get(
        result, 'コンプライアンスダッシュボードで詳細をご確認ください。'
    )
