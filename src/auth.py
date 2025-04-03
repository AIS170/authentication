import os
import boto3
from config import CLIENT_ID, CLIENT_SECRET, DB, POOL_ID, CLIENT_ROLE_ARN
from constants import REGION
import base64
import hmac
import hashlib
from botocore.exceptions import ClientError


def get_cognito():
    return boto3.client("cognito-idp", region_name=REGION)


def get_dynamo():
    sts_client = boto3.client('sts')
    assumed_role_object = sts_client.assume_role(
        RoleArn=CLIENT_ROLE_ARN,
        RoleSessionName="AssumeRoleSession1"
    )
    credentials = assumed_role_object['Credentials']

    aws_access_key_id = credentials['AccessKeyId']
    aws_secret_access_key = credentials['SecretAccessKey']

    session = boto3.Session(
        aws_session_token=credentials['SessionToken'],
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=REGION,
    )
    db = session.resource("dynamodb", region_name=REGION)
    table = db.Table(DB)
    table.load()

    return table


def put_item_to_auth_table(item: dict):
    table = get_dynamo()

    # Write to the table
    response = table.put_item(Item=item)
    return response


def get_error_message(error):
    error_messages = {
            "UsernameExistsException": "The username is already in use.",
            "InvalidPasswordException": "Invalid password provided.",
            "UserNotFoundException": "The user could not be found.",
            "NotAuthorizedException": (
                "You are not authorised to complete this action."
            ),
            "UserNotConfirmedException": "User is not confirmed",
            "ExpiredCodeException": (
                "The provided confirmation code has expired."
            ),
            "CodeMismatchException": (
                "The provided confirmation code is incorrect."
            )
        }

    if isinstance(error, ClientError):
        return (
            error.response['Error']['Code'],
            error_messages.get(
                error.response['Error']['Code'],
                "An unexpected error has occurred"
            )
        )
    else:
        return "UnknownError", "An unexpected error has occurred"


def sign_up(username, email, password, name):
    client = get_cognito()
    table = get_dynamo()

    try:
        secret_hash = generate_secret_hash(username, CLIENT_ID, CLIENT_SECRET)

        ret = client.sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
                {"Name": "preferred_username", "Value": username}
            ],
            SecretHash=secret_hash
        )
        item = {
            "userID": ret["UserSub"],
            "username": username,
            "email": email,
            "name": name,
            "status": "UNCONFIRMED"
        }
        table.put_item(Item=item)

        put_item_to_auth_table(item)

        return {
            "message": (
                "User registered successfully. Please check email "
                "for confirmation code"
            ),
            "user_sub": ret["UserSub"]
        }
    except Exception as error:
        print(error)
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


def confirm_signup(username, conf_code):
    client = get_cognito()
    table = get_dynamo()

    try:
        secret_hash = generate_secret_hash(username, CLIENT_ID, CLIENT_SECRET)

        client.confirm_sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            ConfirmationCode=conf_code,
            SecretHash=secret_hash
        )

        userSub = get_user_sub(username)

        table.update_item(
            Key={"userID": userSub},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "CONFIRMED"}
        )

        return {"message": "Confirmation successfull"}
    except Exception as error:
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


def admin_confirm_signup(username):
    client = get_cognito()

    if os.getenv('TESTING') == 'false':
        return {
            "error_code": "MethodNotAllowed",
            "message": "You are not authorised to perform this action."
        }

    try:
        client.admin_confirm_sign_up(
            UserPoolId=POOL_ID,
            Username=username
        )
        return {"message": "Confirmation successfull"}
    except Exception as error:
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


def login(username, password):
    client = get_cognito()

    try:
        secret_hash = generate_secret_hash(username, CLIENT_ID, CLIENT_SECRET)
        response = client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
                'SECRET_HASH': secret_hash
            }
        )

        id_token = response["AuthenticationResult"]["IdToken"]
        access_token = response["AuthenticationResult"]["AccessToken"]
        refresh_token = response["AuthenticationResult"]["RefreshToken"]

        return {
            "message": "Login Successful",
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except Exception as error:
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


# logout
def logout(access_token):
    client = get_cognito()

    try:
        client.global_sign_out(AccessToken=access_token)
        return {"message": "Logout Successful!"}
    except Exception as error:
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


def delete_user(username, password):
    client = get_cognito()
    table = get_dynamo()

    try:
        secret_hash = generate_secret_hash(username, CLIENT_ID, CLIENT_SECRET)
        client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
                'SECRET_HASH': secret_hash
            }
        )

        client.admin_delete_user(
            UserPoolId=POOL_ID,
            Username=username
        )

        table.delete_item(
            Key={'userID': get_user_sub(username)}
        )

        return {"message": f"User {username} deleted successfully"}
    except Exception as error:
        code, message = get_error_message(error)
        return {
            "error_code": code,
            "message": message
        }


def get_user_sub(username):
    table = get_dynamo()

    response = table.scan(
        FilterExpression="username = :username",
        ExpressionAttributeValues={":username": username}
    )
    if 'Items' in response and len(response['Items']) > 0:
        return response['Items'][0].get('userID')
    else:
        return None


def generate_secret_hash(username, client_id, client_secret):
    message = bytes(username + client_id, 'utf-8')
    clientSecret = bytes(client_secret, 'utf-8')
    dig = hmac.new(clientSecret, message, hashlib.sha256)

    return base64.b64encode(dig.digest()).decode()
