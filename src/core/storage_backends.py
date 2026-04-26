from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    bucket_name = "movbits-media"
    # location = "media/user_uploads"  # S3 prefix/folder
    file_overwrite = False
    default_acl = None
