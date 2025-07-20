"""Development-only middleware for session setup"""
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from addon_service.models import UserReference

logger = logging.getLogger(__name__)


class DevUserSessionMiddleware(MiddlewareMixin):
    """
    Development-only middleware to set user_reference_uri in session.
    This simulates what OSF should be doing before redirecting to Gravyvalet.
    """

    def process_request(self, request):
        if not settings.DEBUG:
            return None

        # Check if we have a valid session but no user_reference_uri
        if (request.session.session_key and
            not request.session.get('user_reference_uri') and
            request.path.startswith('/v1/')):

            # In a real implementation, OSF would set this based on the logged-in user
            # For development, we'll set a default user URI.
            default_user_uri = f"{settings.OSF_BASE_URL}/YOUR_USER_GUID"

            logger.warning(
                f"DEV MODE: Setting user_reference_uri={default_user_uri} in session. "
                "In production, OSF should set this before redirecting to Gravyvalet."
            )

            request.session['user_reference_uri'] = default_user_uri
            request.session.save()

            # Also ensure UserReference exists
            UserReference.objects.get_or_create(user_uri=default_user_uri)
            logger.info(f"DEV MODE: Ensured UserReference exists for {default_user_uri}")

        # Debug logging for user-references endpoint
        if request.path.startswith('/v1/user-references'):
            logger.info(f"User-references request: method={request.method}, "
                       f"user_uri={request.session.get('user_reference_uri')}, "
                       f"query_params={request.GET}")

        return None
