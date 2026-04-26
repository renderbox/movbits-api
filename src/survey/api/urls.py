from django.urls import path

from . import views

urlpatterns = [
    path(
        "interest-list",
        views.add_to_interest_list,
        name="preview_interest_list",
    ),
    path("submit", views.submit_survey, name="preview_submit_survey"),
]


# from django.urls import path

# from survey.api.views import SubmitSurveyView

# urlpatterns = [
#     path("submit/", SubmitSurveyView.as_view(), name="submit-survey"),
# ]
