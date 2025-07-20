import asyncio
from http import HTTPStatus

from asgiref.sync import sync_to_async
from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema

from addon_service.models import (
    OAuth2ClientConfig,
    OAuth2TokenMetadata,
)
from addon_service.oauth2.utils import get_initial_access_token


# Exclude oAuth views from openapi schema as they are from internal use only
@extend_schema(exclude=True)
@transaction.non_atomic_requests  # async views and ATOMIC_REQUESTS do not mix
async def oauth2_callback_view(request):
    """
    Handles oauth callbacks for the GV

    see https://www.rfc-editor.org/rfc/rfc6749.html#section-4.1.2
    """

    # TODO: handle error: https://www.rfc-editor.org/rfc/rfc6749.html#section-4.1.2.1
    _state_token = request.GET["state"]
    _authorization_code = request.GET["code"]
    _token_metadata, _oauth_client_config = await _resolve_state_token(_state_token)
    _fresh_token_result = await get_initial_access_token(
        token_endpoint_url=_oauth_client_config.token_endpoint_url,
        authorization_code=_authorization_code,
        auth_callback_url=_oauth_client_config.auth_callback_url,
        client_id=_oauth_client_config.client_id,
        client_secret=_oauth_client_config.client_secret,
    )
    _accounts = await _token_metadata.update_with_fresh_token(_fresh_token_result)
    await asyncio.gather(*[_account.execute_post_auth_hook() for _account in _accounts])
    
    # TODO: redirect to appropriate page
    # For now, show a simple success message
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>認証完了</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #f5f5f5;
            }
            .message-box {
                text-align: center;
                padding: 40px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #4caf50;
                margin-bottom: 20px;
            }
            p {
                color: #666;
                line-height: 1.6;
            }
        </style>
    </head>
    <body>
        <div class="message-box">
            <h1>Auth done</h1>
            <p>Close this page.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html_content, content_type="text/html")


###
# module-private helpers


@sync_to_async
def _resolve_state_token(
    state_token: str,
) -> tuple[OAuth2TokenMetadata, OAuth2ClientConfig]:
    _token_metadata = OAuth2TokenMetadata.objects.get_by_state_token(state_token)
    return (_token_metadata, _token_metadata.client_details)
