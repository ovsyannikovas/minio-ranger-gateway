# test_gateway_client.py
import os
import boto3
from botocore.client import Config

# Конфигурация
MINIO_ENDPOINT = "http://gateway:8000"  # Адрес вашего gateway
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "fxx9Ukex7mmnwgYrikaY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "mfHAKQRybyqszy6As7MwN9lUl7aeN9JshyDQ4Hty")
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
        print("Buckets:")
        for bucket in response['Buckets']:
            print(f"  - {bucket['Name']} (created: {bucket['CreationDate']})")
        return response
    except Exception as e:
        print(f"Error listing buckets: {e}")
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
        print(f"Object {object_key} uploaded successfully")
        print(f"ETag: {response.get('ETag', 'N/A')}")
        return response
    except Exception as e:
        print(f"Error uploading object: {e}")
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
        print(f"Object {object_key} retrieved successfully")
        print(f"Content: {data.decode('utf-8')}")
        return data
    except Exception as e:
        print(f"Error retrieving object: {e}")
        return None


def list_objects(bucket_name):
    """Пример: список объектов в бакете"""
    s3_client = create_s3_client()
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            print(f"Objects in bucket '{bucket_name}':")
            for obj in response['Contents']:
                print(f"  - {obj['Key']} (size: {obj['Size']} bytes)")
        else:
            print(f"No objects found in bucket '{bucket_name}'")
        return response
    except Exception as e:
        print(f"Error listing objects: {e}")
        return None


def create_bucket(bucket_name):
    """Создать бакет"""
    s3_client = create_s3_client()
    try:
        response = s3_client.create_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' created successfully")
        return response
    except Exception as e:
        print(f"Error creating bucket: {e}")
        return None


if __name__ == "__main__":
    # Пример использования

    # 1. Список бакетов
    print("=== Listing buckets ===")
    list_buckets()

    # 2. Создание бакета (если нужно)
    test_bucket = "my-test-bucket"
    print(f"\n=== Creating bucket '{test_bucket}' ===")
    create_bucket(test_bucket)

    # 3. Загрузка объекта
    print(f"\n=== Uploading object ===")
    put_object(test_bucket, "test-object.txt", b"Hello from boto3 client!")

    # 4. Получение объекта
    print(f"\n=== Retrieving object ===")
    get_object(test_bucket, "def.json")

    # 5. Список объектов в бакете
    print(f"\n=== Listing objects in bucket ===")
    list_objects(test_bucket)

    # 6. Еще раз список бакетов
    print(f"\n=== Final bucket list ===")
    list_buckets()