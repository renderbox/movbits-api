from django.urls import path

from . import views

urlpatterns = [
    path("upload-batches/", views.create_upload_batch, name="media_create_batch"),
    path(
        "upload-batches/<uuid:batch_id>/",
        views.upload_batch_detail,
        name="media_batch_detail",
    ),
    path(
        "upload-batches/<uuid:batch_id>/files/<uuid:file_id>/complete/",
        views.complete_file_upload,
        name="media_complete_file",
    ),
    path("uploads/", views.list_uploads, name="media_list_uploads"),
]
