import copy
from logging import getLogger

from django.db.models import Prefetch, Q, Case, When, Value, BooleanField

from conpass.models import User, Directory, DirectoryPermission, Group

logger = getLogger(__name__)


class DirectoryService:

    def get_allowed_directories(self, user: User, type: int) -> [Directory]:
        """
        そのユーザが許可されているディレクトリ一覧を返す
        """
        wheres = {
            'status': Directory.Status.ENABLE.value,
            'account': user.account,
            'type': type
        }
        try:
            prefetch = self.get_permission_prefetch(user)
            directories = list(
                Directory.objects.filter(**wheres)
                .all().annotate(
                    sort_id_is_null=Case(
                        When(sort_id__isnull=True, then=Value(True)),
                        default=Value(False),
                        output_field=BooleanField()
                    )
                ).order_by('sort_id_is_null', 'sort_id', 'name')
                .prefetch_related(prefetch))
        except Exception as e:
            logger.error(e)
            raise e

        # フォルダの表示制限
        # ユーザかグループのいずれかで許可があれば許可とします（そうしないとグループとユーザ両方にチェックを入れ続けることになる）
        allowed_directories = self.filter_visible_directories(directories, user.is_bpo)
        return allowed_directories

    def get_permission_prefetch(self, user: User, prefetch_name='directory_permission_directory'):
        """
        階層の表示可否設定の情報を付与する
        user.is_bpo = true であれば無条件になる
        """
        if user.is_bpo:
            return None

        permission_wheres = {
            'is_visible': True,
            'status': DirectoryPermission.Status.ENABLE.value,
        }
        my_groups = list(Group.objects.filter(user_group=user, status=Group.Status.ENABLE.value).all())
        return Prefetch(prefetch_name,
                        queryset=DirectoryPermission.objects.filter(Q(**permission_wheres),
                                                                    Q(user=user) | Q(group__in=my_groups))
                        .select_related('user', 'group'),
                        to_attr='permissions'
                        )

    def filter_visible_directories(self, directories: [Directory], show_all=False) -> [Directory]:
        """
        表示設定が有効な階層だけを返す
        prefetchでpermissionsを付与してください
        """
        remove_directories = []
        try:
            for directory in directories:
                if not show_all and isinstance(directory.permissions, list) and len(directory.permissions) == 0:
                    remove_directories.append(directory)
                    # これが親階層なら子階層も全部見えなくなる
                    if directory.level == 0:
                        for subdir in directories:
                            if subdir.level == 1 and subdir.parent_id == directory.id:
                                remove_directories.append(subdir)
            result = directories.copy()
            for remove_dir in remove_directories:
                if remove_dir in result:
                    result.remove(remove_dir)

        except Exception as e:
            logger.error(e)
            raise e

        return result
