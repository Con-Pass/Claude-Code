import pytest
#from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
User = get_user_model()

@pytest.mark.django_db
class TestIndexView:
    def test_index(self):
        assert User.objects.count() == 0


@pytest.mark.django_db
def test_model():
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_model_2():
    assert User.objects.count() == 0
