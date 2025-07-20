"""Development-only permission classes with URI normalization"""
import logging
from django.conf import settings
from urllib.parse import urlparse, urlunparse
from django.http.request import QueryDict
from rest_framework import serializers

from .permissions import SessionUserIsOwner as BaseSessionUserIsOwner
from .get_user_uri import get_user_uri
from .filtering import RestrictedListEndpointFilterBackend, extract_filter_expressions

logger = logging.getLogger(__name__)


def normalize_user_uri(uri):
    """
    Normalize user URIs to handle hostname variations in development.

    In development, the same user might be referenced with different hostnames:
    - http://localhost:5000/user123
    - http://192.168.168.167:5000/user123
    - http://127.0.0.1:5000/user123

    This function normalizes these to use the configured OSF_BASE_URL.
    """
    if not uri:
        return uri

    parsed = urlparse(uri)
    osf_parsed = urlparse(settings.OSF_BASE_URL)

    # In development, normalize known local hostnames to match OSF_BASE_URL
    if settings.DEBUG and parsed.hostname in ['localhost', '127.0.0.1', '192.168.168.167']:
        normalized = parsed._replace(
            scheme=osf_parsed.scheme,
            netloc=osf_parsed.netloc
        )
        normalized_uri = urlunparse(normalized)
        logger.debug(f"Normalized URI: {uri} -> {normalized_uri}")
        return normalized_uri

    return uri


class DevSessionUserIsOwner(BaseSessionUserIsOwner):
    """Development version of SessionUserIsOwner with URI normalization"""

    def has_object_permission(self, request, view, obj):
        session_user_uri = get_user_uri(request)

        if not session_user_uri:
            return False

        # Normalize both URIs for comparison
        normalized_session_uri = normalize_user_uri(session_user_uri)
        normalized_obj_uri = normalize_user_uri(obj.owner_uri)

        logger.info(
            f"DevSessionUserIsOwner permission check:\n"
            f"  Original session URI: {session_user_uri}\n"
            f"  Original object URI: {obj.owner_uri}\n"
            f"  Normalized session URI: {normalized_session_uri}\n"
            f"  Normalized object URI: {normalized_obj_uri}\n"
            f"  Match: {normalized_session_uri == normalized_obj_uri}"
        )

        return normalized_session_uri == normalized_obj_uri


class DevRestrictedListEndpointFilterBackend(RestrictedListEndpointFilterBackend):
    """Development version of RestrictedListEndpointFilterBackend with URI normalization"""

    def filter_queryset(self, request, queryset, view):
        if view.action != "list":
            return queryset

        required_filters = set(view.required_list_filter_fields)
        filter_expressions = extract_filter_expressions(
            request.query_params, view.get_serializer()
        )

        # Normalize user_uri filter in development
        if 'user_uri' in filter_expressions and settings.DEBUG:
            original_uri = filter_expressions['user_uri']
            normalized_uri = normalize_user_uri(original_uri)
            filter_expressions['user_uri'] = normalized_uri

            logger.info(
                f"DevRestrictedListEndpointFilterBackend: "
                f"Normalized filter user_uri: {original_uri} -> {normalized_uri}"
            )

        missing_filters = required_filters - filter_expressions.keys()
        if missing_filters:
            raise serializers.ValidationError(
                f"Request was missing the following required filters for this endpoint: {missing_filters}"
            )

        return queryset.filter(**filter_expressions)
