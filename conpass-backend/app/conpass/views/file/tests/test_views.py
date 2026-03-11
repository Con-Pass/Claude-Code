import pytest

from conpass.tests.factories.file import FileFactory


@pytest.fixture
def page_size(settings):
    settings.REST_FRAMEWORK['PAGE_SIZE'] = 10


class TestFileListView:
    @pytest.mark.django_db
    def test_get__paginate_10(self, api_client, login_user, page_size):
        FileFactory.create_batch(10, account=login_user.account)
        response = api_client.get('/api/file/all')
        assert 200 == response.status_code, response.data
        assert 10 == len(response.data['results'])
        assert 10 == response.data['page_total']
        assert 1 == response.data['page_number']
        assert 1 == response.data['page_count']

    @pytest.mark.django_db
    def test_get__paginate_11__page1(self, api_client, login_user, page_size):
        FileFactory.create_batch(11, account=login_user.account)

        response = api_client.get('/api/file/all')

        assert 200 == response.status_code, response.data
        assert 10 == len(response.data['results'])
        assert 11 == response.data['page_total']
        assert 1 == response.data['page_number']
        assert 2 == response.data['page_count']

    @pytest.mark.django_db
    def test_get__paginate_11__page2(self, api_client, login_user, page_size):
        FileFactory.create_batch(11, account=login_user.account)

        response = api_client.get('/api/file/all', {
            'page': 2,
        })

        assert 200 == response.status_code, response.data
        assert 1 == len(response.data['results'])
        assert 11 == response.data['page_total']
        assert 2 == response.data['page_number']
        assert 2 == response.data['page_count']

    @pytest.mark.django_db
    def test_get__paginate_11__page3(self, api_client, login_user, page_size):
        FileFactory.create_batch(11, account=login_user.account)

        response = api_client.get('/api/file/all', {
            'page': 3,
        })

        assert 404 == response.status_code, response.data
        assert '不正なページです。' == response.data['detail']
