import json

from src.auth import get_item_from_DB

def test_verify_signup(client, mock_cognito, user_data_1, clear_dynamo):
    client.post(
        '/signup', data=json.dumps(user_data_1),
        content_type='application/json'
    )

    item = get_item_from_DB(user_data_1['username'])

    assert item is not None
    assert item['username'] == user_data_1['username']
    assert item['email'] == user_data_1['email']
    assert item['status'] == 'UNCONFIRMED'


def test_verify_confirm_signup(client, mock_cognito, user_data_1, clear_dynamo):
    client.post(
        '/signup', data=json.dumps(user_data_1),
        content_type='application/json'
    )

    client.post(
        '/admin/confirm_signup',
        data=json.dumps({'username': user_data_1['username']}),
        content_type='application/json'
    )

    item = get_item_from_DB(user_data_1['username'])

    assert item is not None
    assert item['username'] == user_data_1['username']
    assert item['email'] == user_data_1['email']
    assert item['status'] == 'CONFIRMED'


def test_verify_user_delete(client, mock_cognito, user_data_1, clear_dynamo):
    ret = client.post(
        '/signup', data=json.dumps(user_data_1),
        content_type='application/json'
    )
    assert ret.status_code == 200

    item = get_item_from_DB(user_data_1['username'])

    assert item is not None
    assert item['username'] == user_data_1['username']
    assert item['email'] == user_data_1['email']
    assert item['status'] == 'UNCONFIRMED'

    ret = client.post(
        '/admin/confirm_signup',
        data=json.dumps({'username': user_data_1['username']}),
        content_type='application/json'
    )
    assert ret.status_code == 200

    ret = client.delete(
        '/delete_user',
        data=json.dumps({'username': user_data_1['username'], 'password': user_data_1['password']}),
        content_type='application/json'
    )
    assert ret.status_code == 200

    item = get_item_from_DB(user_data_1['username'])

    assert item is None

def test_signup_no_corruption(client, mock_cognito, user_data_1, clear_dynamo):
    data = {
        'email': 'john.doe@example.com',
        'password': 'goodPassword123!',
        'name': 'John Doe'
    }
    ret = client.post(
        '/signup', data=json.dumps(data),
        content_type='application/json'
    )
    assert ret.status_code == 400

    item = get_item_from_DB(user_data_1['username'])

    assert item is None


def test_confirm_signup_no_corruption(client, mock_cognito, user_data_1, clear_dynamo):
    ret = client.post(
        '/signup', data=json.dumps(user_data_1),
        content_type='application/json'
    )
    assert ret.status_code == 200

    ret = client.post(
        '/confirm_signup',
        data=json.dumps({'username': user_data_1['username']}),
        content_type='application/json'
    )
    assert ret.status_code == 400

    item = get_item_from_DB(user_data_1['username'])

    assert item is not None
    assert item['username'] == user_data_1['username']
    assert item['email'] == user_data_1['email']
    assert item['status'] == 'UNCONFIRMED'
