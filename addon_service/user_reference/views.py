from django.conf import settings
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

from addon_service.common.permissions import SessionUserIsOwner
from addon_service.common.viewsets import RestrictedReadOnlyViewSet

from .models import UserReference
from .serializers import UserReferenceSerializer

# Use development permission class with URI normalization in DEBUG mode
if settings.DEBUG:
    from addon_service.common.dev_permissions import DevSessionUserIsOwner
    _permission_class = DevSessionUserIsOwner
else:
    _permission_class = SessionUserIsOwner



@extend_schema_view(
    list=extend_schema(
        description="Get user reference by user_uri. Even through this is a list method, this endpoint returns only one entity"
    ),
    retrieve=extend_schema(
        description="Get user reference by it's pk",
    ),
)
class UserReferenceViewSet(RestrictedReadOnlyViewSet):
    queryset = UserReference.objects.all()
    serializer_class = UserReferenceSerializer
    permission_classes = [
        _permission_class,
    ]
    allowed_query_params = ["uris"]
    # Satisfies requirements of `RestrictedReadOnlyViewSet.list`
    required_list_filter_fields = ("user_uri",)
