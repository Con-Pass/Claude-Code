from rest_framework import serializers

from conpass.models import user, User, PermissionCategoryKey


class UserRequestBodySerializer(serializers.Serializer):
    userName = serializers.CharField(allow_blank=True, required=False)
    type = serializers.ChoiceField(
        required=False,
        default=User.Type.ACCOUNT.value,
        choices=(
            (User.Type.ACCOUNT.value, User.Type.ACCOUNT.value),
            (User.Type.CLIENT.value, User.Type.CLIENT.value),
        ),
    )
    clientId = serializers.IntegerField(required=False)
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UserDeleteRequestBodySerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    username = serializers.CharField()  # 名前
    email = serializers.CharField()  # メールアドレス
    type = serializers.CharField()  # ロール
    status = serializers.IntegerField()  # ステータス
    mfaStatus = serializers.IntegerField(source='mfa_status')  # 2段階認証ステータス
    lastLogin = serializers.DateTimeField(source='last_login', format="%Y-%m-%d %H:%M:%S")  # 最終ログイン
    permission_category_id = serializers.SerializerMethodField()
    permission_category_name = serializers.SerializerMethodField()

    def get_permission_category_id(self, obj):
        return obj.permission_category_id

    def get_permission_category_name(self, obj):
        permission_category_id = obj.permission_category_id
        try:
            if permission_category_id is not None:
                permission_category_key = PermissionCategoryKey.objects.get(id=permission_category_id)
                return permission_category_key.name
            else:
                return "カスタム"
        except PermissionCategoryKey.DoesNotExist:
            return "カスタム"


class UserResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=UserResponseSerializer(),
        allow_empty=True
    )


class UserDataRequestBodySerializer(serializers.Serializer):
    userName = serializers.CharField(allow_null=True, required=False)
    userType = serializers.IntegerField(default=1, allow_null=True, required=False)
    clientId = serializers.IntegerField(allow_null=True, required=False)
    isBpo = serializers.BooleanField(default=False, allow_null=True, required=False)
    """
    request body serializer
    APIのパラメータをバリデートします
    """

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UserDataResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    userName = serializers.CharField(source='username')  # 名前
    type = serializers.CharField()  # ロール
    division = serializers.CharField()
    position = serializers.CharField()
    tel = serializers.CharField()
    memo = serializers.CharField()
    email = serializers.CharField()
    mfaStatus = serializers.IntegerField(source='mfa_status')  # 2段階認証ステータス
    isBpoAdmin = serializers.BooleanField(source='is_bpo_admin')  # BPO契約管理者
    isBpo = serializers.BooleanField(source='is_bpo')  # BPOユーザーかどうか
    clientName = serializers.CharField(source='client.name', allow_null=type)  # 連絡先（type=2の時）
    corporateName = serializers.CharField(source='corporate.name', allow_null=type)  # 法人名（あれば）


class UserDataResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=UserDataResponseSerializer(),
        allow_empty=True
    )


class UserPermissionsTargetSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # 対象のID
    name = serializers.CharField()  # 対象の名前
    sort_id= serializers.IntegerField(required=False)


class UserPermissionsRequstSerializer(serializers.Serializer):
    target = UserPermissionsTargetSerializer()
    isAllow = serializers.BooleanField()  # 許可されているかどうか


class UserPermissionsResponseSerializer(serializers.Serializer):
    target = UserPermissionsTargetSerializer()
    isAllow = serializers.BooleanField(source='is_allow')  # 許可されているかどうか


class UserPermissionsRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    permission_category_id = serializers.IntegerField(allow_null=True)
    permissions = serializers.ListField(
        child=UserPermissionsRequstSerializer()
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UserPermissionCategoryRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    editing = serializers.BooleanField()
    checked = serializers.BooleanField()
    permissions = serializers.ListField(
        child=UserPermissionsRequstSerializer()
    )

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class UserPermissionsResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=UserPermissionsResponseSerializer(),
        allow_empty=True
    )


class UserPermissionCategoryNameResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 名前
    editing = serializers.BooleanField()
    checked = serializers.BooleanField()
    permissions = serializers.ListField(
        child=UserPermissionsResponseSerializer()
    )


class UserPermissionCategoryResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListSerializer(
        child=UserPermissionCategoryNameResponseSerializer(),
        allow_empty=True
    )


class UserPermissionsUserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()  # userID
    username = serializers.CharField()  # 名前
    email = serializers.CharField()  # メールアドレス
    permission_category_id = serializers.SerializerMethodField()
    permission_category_name = serializers.SerializerMethodField()
    permissions = serializers.ListField(
        child=UserPermissionsResponseSerializer()
    )

    def get_permission_category_id(self, obj):
        return obj.permission_category_id

    def get_permission_category_name(self, obj):
        permission_category_id = obj.permission_category_id
        try:
            if permission_category_id is not None:
                permission_category_key = PermissionCategoryKey.objects.get(id=permission_category_id)
                return permission_category_key.name
            else:
                return "カスタム"
        except PermissionCategoryKey.DoesNotExist:
            return "カスタム"


class UserPermissionsListResponseBodySerializer(serializers.Serializer):

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=UserPermissionsUserResponseSerializer(),
        allow_empty=True
    )
