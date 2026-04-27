import datetime

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from survey.models import InterestedUser, Survey, SurveyResult

User = get_user_model()


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


@api_view(["POST"])
def add_to_interest_list(request):
    """
    POST /api/v1/preview/interest-list
    Body: { email: string }
    Returns InterestListResponse:
      {
        success: boolean,
        alreadyRegistered: boolean,
        message: string,
        surveyEligible: boolean,
        surveyQuestions?: [...],
        surveyId?: string
      }
    """

    # get or create InterestedUser
    email = request.data.get("email")
    interested, created = InterestedUser.objects.get_or_create(
        email=email, site=Site.objects.get(id=1)
    )  # TODO: handle site properly.  This is a placeholder.  Site ID should be set in middleware from the requesting app.

    # print("Adding to interest list:", email, created)

    if created:
        interested.save()
    else:
        return Response(
            {
                "success": True,
                "alreadyRegistered": True,
                "message": "Already registered",
                "surveyEligible": False,
            },
            status=status.HTTP_200_OK,
        )

    # print("checking for survey eligibility...")

    survey = (
        Survey.objects.filter(
            is_active=True, survey_type=Survey.TypeChoices.PRE_PREVIEW
        )
        .order_by("-created_at")
        .first()
    )

    if not survey or not survey.questions:
        # change this to a warning log entry

        return Response(
            {
                "success": True,
                "alreadyRegistered": False,
                "message": "Added to interest list",
                "surveyEligible": False,
            },
            status=status.HTTP_201_CREATED,
        )

    # The user is eligible for survey if they don't have a SurveyResult yet

    response = {
        "success": True,
        "alreadyRegistered": not created,
        "message": ("Added to interest list" if created else "Already registered"),
        "surveyEligible": False,
    }

    # check if they have taken this survey before
    if not SurveyResult.objects.filter(email=email, survey=survey).exists():
        response["surveyId"] = survey.uuid
        response["surveyEligible"] = True
        response["surveyQuestions"] = survey.questions

    # print("Response prepared:", response)

    return Response(
        response,
        status=(status.HTTP_201_CREATED if created else status.HTTP_200_OK),
    )


@api_view(["POST"])
def submit_survey(request):
    """
    POST /api/v1/survey/submit
    Body: { surveyId: string, email: string, responses: [{questionId, answer}] }
    Returns SurveySubmissionResponse:
      { success: boolean, message: string, submissionId?: string }
    """

    # print out the incoming data for debugging

    # site = Site.objects.get(id=1)  # TODO: handle site properly. Placeholder.

    SurveyResult.objects.create(
        email=request.data.get("email"),
        responses=request.data.get("responses"),
        survey=Survey.objects.get(uuid=request.data.get("surveyId")),
    )

    return Response(
        {
            "success": True,
            "message": "Survey submitted",
        }
    )


# class SubmitSurveyView(APIView):
#     """
#     POST: Submit survey responses. Requires email or authenticated user.
#     """

#     def post(self, request):
#         email = request.data.get("email")
#         user = request.user if request.user.is_authenticated else None
#         responses = request.data.get("responses")

#         if not email and not user:
#             return Response(
#                 {"success": False, "message": "Email or login required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         if not responses:
#             return Response(
#                 {"success": False, "message": "Survey responses required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         survey_result = SurveyResults.objects.create(
#             email=email if email else user.email,
#             user=user,
#             responses=responses,
#         )
#         return Response(
#             {"success": True, "message": "Survey submitted."},
#             status=status.HTTP_201_CREATED,
#         )
