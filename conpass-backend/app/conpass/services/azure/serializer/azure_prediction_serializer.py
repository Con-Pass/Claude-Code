from rest_framework import serializers


class PredictionSerializer(serializers.Serializer):
    filename = serializers.CharField()  # gcsのパス
    entity = serializers.CharField()  # 項目名に相当（conpayaなど）
    score = serializers.FloatField()  # 解析した時のスコア（0.0～1.0、高いほど良い）
    content = serializers.CharField()  # 読み取った値。誤字が結構ある
    start = serializers.IntegerField()  # 読み取り開始行
    end = serializers.IntegerField()  # 読み取り終了行

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass


class PredictionPerFilesSerializer(serializers.Serializer):
    predictions = serializers.ListField(
        child=PredictionSerializer(),
        allow_empty=True
    )
    body = serializers.CharField()
    pdf_page_size = serializers.IntegerField()


class PredictionListSerializer(serializers.Serializer):
    files = serializers.ListField(  # ファイル単位の配列
        child=PredictionPerFilesSerializer(),
        allow_empty=True
    )
