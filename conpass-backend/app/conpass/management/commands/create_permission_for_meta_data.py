from django.core.management import BaseCommand
from conpass.models import PermissionCategoryKey, PermissionCategory, User, Permission


class Command(BaseCommand):
    help='Create permission of edit meta data for existing permissions and permission categories'
    def handle(self, *args, **kwargs):
        print("started creating the data for PermissionCatgegory >>>>>")
        permission_category_row=PermissionCategoryKey.objects.filter(account_id__isnull=False)
        for permission_category in permission_category_row:
            perm_catgory=PermissionCategory.objects.filter(permission_category=permission_category).first()
            if perm_catgory:
                perm_catgory.pk=None
                perm_catgory.is_allow=False
                perm_catgory.target_id=14
                perm_catgory.status=1
                perm_catgory.save()
        print("Finished creating the data for Permission Catgegory <<<<")

        print("started creating the data for Permission >>>>>")
        users= User.objects.all()
        for user in users:
            perm= Permission.objects.filter(user=user).first()
            if perm:
                perm.pk=None
                perm.is_allow = False
                perm.target_id=14
                perm.status = 1
                perm.save()
        print("Finished creating the data for Permission >>>>>")








