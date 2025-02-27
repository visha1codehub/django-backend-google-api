# api/views.py
from django.http import JsonResponse, HttpResponse
from rest_framework.views import APIView
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials  # Import this
from googleapiclient.http import MediaIoBaseUpload  # Import this
import json
from django.conf import settings
from icecream import ic
import mimetypes

# 1. Google Authentication
class GoogleAuthView(APIView):
    def get(self, request):
        flow = InstalledAppFlow.from_client_config({
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }, scopes=['https://www.googleapis.com/auth/drive'])

        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        request.session['state'] = state
        return JsonResponse({'authorization_url': authorization_url})

class GoogleAuthCallbackView(APIView):
    def get(self, request):
        state = request.session.get('state')
        flow = InstalledAppFlow.from_client_config({
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }, scopes=['https://www.googleapis.com/auth/drive'])

        ic(request.build_absolute_uri())
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        absolute_uri = request.build_absolute_uri().replace('http://', 'https://', 1)
        flow.fetch_token(authorization_response=absolute_uri)
        credentials = flow.credentials
        return JsonResponse({
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expires_in': credentials.expiry.isoformat()
        })

# 2. Google Drive Integration
class DriveIntegrationView(APIView):
    def post(self, request):
        # Get credentials from request
        credentials_raw = request.data.get('credentials')

        # Handle different input types
        if isinstance(credentials_raw, str):
            # Case: form-data sends credentials as a JSON string
            credentials_dict = json.loads(credentials_raw)
        elif isinstance(credentials_raw, dict):
            # Case: raw JSON sends credentials as a parsed dict
            credentials_dict = credentials_raw
        else:
            return JsonResponse({'error': 'Invalid credentials format'}, status=400)
        # Convert dict to Credentials object
        credentials = Credentials(
            token=credentials_dict.get('token'),
            refresh_token=credentials_dict.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET
        )

        # Build the Drive service
        service = build('drive', 'v3', credentials=credentials)

        # Upload file
        if 'file' in request.FILES:
            file_metadata = {'name': request.FILES['file'].name}
            # Convert UploadedFile to MediaIoBaseUpload
            media = MediaIoBaseUpload(
                request.FILES['file'],  # File-like object
                mimetype=request.FILES['file'].content_type or 'application/octet-stream'
            )
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return JsonResponse({'file_id': file.get('id')})

        file_id = request.data.get('file_id')
        if file_id:
            # Get file metadata to determine MIME type
            file_metadata = service.files().get(fileId=file_id, fields='mimeType, name').execute()
            mime_type = file_metadata.get('mimeType', 'application/octet-stream')
            file_name = file_metadata.get('name', 'downloaded_file')

            # Download the file content
            file_content = service.files().get_media(fileId=file_id).execute()

            # Return binary content with proper MIME type
            response = HttpResponse(file_content, content_type=mime_type)
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response

        return JsonResponse({'error': 'Invalid request'}, status=400)

