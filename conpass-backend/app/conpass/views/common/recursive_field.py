from rest_framework import serializers


class RecursiveField(serializers.Field):
    """
    自分と同じモデルを参照する時にシリアライザーで指定する
    無限再起防止のために、recurse_target で対象のフィールド名を指定する
    例：Contract は template と origin が 同じ Contract モデル
    レスポンスシリアライザーで以下のように指定する
    template = RecursiveField(allow_null=True, recurse_targets=['template', 'origin'])
    origin = RecursiveField(allow_null=True, recurse_targets=['template', 'origin'])
    """

    def __init__(self, recurse_targets: [str], **kwargs):
        super().__init__()
        self.targets = recurse_targets

    def to_representation(self, obj):
        parent = self.parent.__class__(obj, processed=self.parent.processed)
        for target in self.targets:
            if getattr(obj, target) in self.parent.processed:
                return
            self.parent.processed.add(getattr(obj, target))
        return parent.data
