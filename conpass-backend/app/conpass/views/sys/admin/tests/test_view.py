import pytest

from conpass.models import User
from conpass.tests.factories.user import UserFactory


@pytest.mark.django_db
def test__list(sys_client):
    UserFactory.create_batch(3, type=User.Type.ADMIN.value)
    response = sys_client.get('/api/sys/admin/all')
    assert 4 == len(response.data['results'])


@pytest.mark.django_db
def test__delete(sys_client):
    admin = UserFactory(type=User.Type.ADMIN.value)
    response = sys_client.delete('/api/sys/admin/delete', {
        'ids': [admin.id]
    })
    assert response.data['success']
    assert not User.objects.filter(id=admin.id, status=User.Status.ENABLE.value).exists()


@pytest.mark.django_db
def test__detail(sys_client):
    admin: User = UserFactory(type=User.Type.ADMIN.value)
    response = sys_client.get('/api/sys/admin/detail', {
        'id': admin.id
    })

    assert admin.login_name == response.data['login_name']
    assert admin.username == response.data['username']
    assert admin.email == response.data['email']


class TestNew:
    @pytest.mark.django_db
    def test__new(self, sys_client):
        response = sys_client.post('/api/sys/admin/new', {
            'loginName': 'foo',
            'password': '3g60549ju',
            'email': 'admin001@example.com',
            'username': 'user name',
        })

        assert 'foo' == response.data['login_name']
        assert 'admin001@example.com' == response.data['email']
        assert 'user name' == response.data['username']
        actual = User.objects.get(pk=response.data['id'])
        assert 'foo' == actual.login_name
        assert 'admin001@example.com' == actual.email
        assert 'user name' == actual.username

    @pytest.mark.parametrize('case,password,login_name,email,username,expected_status', [
        ['OK:正常', '3g60549ju', 'adminUserName', 'admin001@example.com', 'user name', 200],
        ['NG:ログインIDと似ている', 'adminUserNam', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:メールアドレスと似ている', 'admin001@example.co', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:名前と似ている', 'usr nam', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:よくある文字列', 'abcdefgh', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:8文字未満', '3g6Aga2', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:数字だけ', '123456789', 'adminUserName', 'admin001@example.com', 'user name', 400],
    ])
    @pytest.mark.django_db
    def test__new__validate_password(self, sys_client, case, password, login_name, email, username, expected_status):
        response = sys_client.post('/api/sys/admin/new', {
            'loginName': login_name,
            'password': password,
            'email': email,
            'username': username,
        })

        assert response.status_code == expected_status


class TestEdit:
    @pytest.mark.django_db
    def test__edit(self, sys_client):
        admin: User = UserFactory(type=User.Type.ADMIN.value)
        response = sys_client.post('/api/sys/admin/edit', {
            'id': admin.id,
            'loginName': 'foo',
            'password': '3g60549ju',
            'email': 'admin001@example.com',
            'username': 'user name',
        })

        assert admin.id == response.data['id']
        assert 'foo' == response.data['login_name']
        assert 'admin001@example.com' == response.data['email']
        assert 'user name' == response.data['username']
        actual = User.objects.get(pk=admin.id)
        assert 'foo' == actual.login_name
        assert 'admin001@example.com' == actual.email
        assert 'user name' == actual.username

    @pytest.mark.django_db
    def test__edit__invalid(self, sys_client):
        UserFactory(type=User.Type.ADMIN.value)
        response = sys_client.post('/api/sys/admin/edit', {
            'loginName': 'foo',
            'password': '3g60549ju',
            'email': 'admin001@example.com',
            'username': 'user name',
        })

        assert 400 == response.status_code

    @pytest.mark.parametrize('case,password,login_name,email,username,expected_status', [
        ['OK:正常', '3g60549ju', 'adminUserName', 'admin001@example.com', 'user name', 200],
        ['NG:ログインIDと似ている', 'adminUserNam', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:メールアドレスと似ている', 'admin001@example.co', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:名前と似ている', 'usr nam', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:よくある文字列', 'abcdefgh', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:8文字未満', '3g6Aga2', 'adminUserName', 'admin001@example.com', 'user name', 400],
        ['NG:数字だけ', '123456789', 'adminUserName', 'admin001@example.com', 'user name', 400],
    ])
    @pytest.mark.django_db
    def test__edit__validate_password(self, sys_client, case, password, login_name, email, username, expected_status):
        admin: User = UserFactory(type=User.Type.ADMIN.value)
        response = sys_client.post('/api/sys/admin/edit', {
            'id': admin.id,
            'loginName': login_name,
            'password': password,
            'email': email,
            'username': username,
        })

        assert response.status_code == expected_status
