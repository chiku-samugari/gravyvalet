"""Development-only permission classes with URI normalization"""
import logging
from django.conf import settings
from urllib.parse import urlparse, urlunparse

from .permissions import SessionUserIsOwner as BaseSessionUserIsOwner
from .get_user_uri import get_user_uri

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
