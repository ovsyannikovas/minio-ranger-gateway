# test_gateway_client.py
import os

import boto3
from botocore.client import Config

# Конфигурация
MINIO_ENDPOINT = "http://gateway:8000"  # Адрес вашего gateway
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "kcUiX3e6EJYfhFOEFqXB")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "2dFcuDNJDfkclLTbueiQDpQHVDcZpFFwpriCDkjx")
REGION = "us-east-1"


def create_s3_client():
    """Создает S3 клиент для работы с MinIO gateway"""
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
        config=Config(signature_version='s3v4'),  # Важно для MinIO
        verify=False  # Отключаем проверку SSL для тестов
    )


def list_buckets():
    """Пример: список бакетов"""
    s3_client = create_s3_client()
    try:
        response = s3_client.list_buckets()
        for _bucket in response['Buckets']:
            pass
        return response
    except Exception:
        return None


def put_object(bucket_name, object_key, data):
    """Пример: создать/обновить объект"""
    s3_client = create_s3_client()
    try:
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=data
        )
        return response
    except Exception:
        return None


def get_object(bucket_name, object_key):
    """Пример: получить объект"""
    s3_client = create_s3_client()
    try:
        response = s3_client.get_object(
            Bucket=bucket_name,
            Key=object_key
        )
        data = response['Body'].read()
        return data
    except Exception:
        return None


def list_objects(bucket_name):
    """Пример: список объектов в бакете"""
    s3_client = create_s3_client()
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for _obj in response['Contents']:
                pass
        else:
            pass
        return response
    except Exception:
        return None


def create_bucket(bucket_name):
    """Создать бакет"""
    s3_client = create_s3_client()
    try:
        response = s3_client.create_bucket(Bucket=bucket_name)
        return response
    except Exception:
        return None


if __name__ == "__main__":
    # Пример использования

    # 1. Список бакетов
    list_buckets()

    # 2. Создание бакета (если нужно)
    test_bucket = "my-test-bucket"
    create_bucket(test_bucket)

    # 3. Загрузка объекта
    put_object(test_bucket, "test-object.txt", b"Hello from boto3 client!")

    # 4. Получение объекта
    get_object(test_bucket, "def.json")

    # 5. Список объектов в бакете
    list_objects(test_bucket)

    # 6. Еще раз список бакетов
    list_buckets()
