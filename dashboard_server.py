import uvicorn
import os
import json
import time
import httpx
import secrets
import urllib.parse
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer

# Load environment variables
load_dotenv()

# Configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:9091/api/auth/callback')
SECRET_KEY = os.getenv('SECRET_KEY', 'dev_secret_key_change_me')

serializer = URLSafeSerializer(SECRET_KEY)

# Define the standalone FastAPI app
app = FastAPI(title="Chronix Dashboard Standalone", openapi_url=None, docs_url=None, redoc_url=None)

# Basic CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Helpers ---
def get_user_from_cookie(request: Request):
    token = request.cookies.get("chronix_session")
    if not token:
        return None
    try:
        data = serializer.loads(token)
        return data
    except Exception:
        return None

# --- Auth Routes ---
@app.get('/api/auth/login')
async def login():
    if not DISCORD_CLIENT_ID:
        return JSONResponse({'error': 'OAuth not configured'}, status_code=500)
    
    # Generate a random state for CSRF protection
    state = secrets.token_urlsafe(16)
    
    scope = "identify guilds"
    redirect_uri_encoded = urllib.parse.quote(DISCORD_REDIRECT_URI)
    
    discord_url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={DISCORD_CLIENT_ID}&"
        f"redirect_uri={redirect_uri_encoded}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"state={state}"
    )
    
    response = RedirectResponse(discord_url)
    
    # Store state in a short-lived, signed cookie
    state_token = serializer.dumps(state)
    response.set_cookie(
        key="oauth_state", 
        value=state_token, 
        httponly=True, 
        max_age=300, # 5 minutes
        samesite='lax'
    )
    
    return response

@app.get('/api/auth/callback')
async def callback(request: Request, code: str, state: str):
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET):
        return JSONResponse({'error': 'OAuth not configured'}, status_code=500)

    # Verify State
    cookie_state_token = request.cookies.get("oauth_state")
    if not cookie_state_token:
        return JSONResponse({'error': 'State cookie missing or expired. Please try logging in again.'}, status_code=400)
    
    try:
        cookie_state = serializer.loads(cookie_state_token)
    except Exception:
         return JSONResponse({'error': 'Invalid state cookie.'}, status_code=400)
         
    if not secrets.compare_digest(state, cookie_state):
         return JSONResponse({'error': 'State mismatch! Potential CSRF attack.'}, status_code=400)

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            r = await client.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
            r.raise_for_status()
            tokens = r.json()
            access_token = tokens.get('access_token')
            
            # Fetch User Info
            user_r = await client.get('https://discord.com/api/users/@me', headers={
                'Authorization': f"Bearer {access_token}"
            })
            user_r.raise_for_status()
            user_data = user_r.json()
            
            # Prepare Session Data
            session_data = {
                'id': user_data['id'],
                'username': user_data['username'],
                'avatar': user_data['avatar'],
                'discriminator': user_data.get('discriminator', '0'),
                'access_token': access_token
            }
            
            # Create Session Cookie
            encrypted_session = serializer.dumps(session_data)
            response = RedirectResponse(url='/') # Redirect to dashboard home
            
            # Set session cookie
            response.set_cookie(key="chronix_session", value=encrypted_session, httponly=True, samesite='lax')
            
            # Clear state cookie
            response.delete_cookie("oauth_state")
            
            return response

        except httpx.HTTPStatusError as e:
            print(f"OAuth Error: {e.response.text}")
            return JSONResponse({'error': 'Failed to authenticate with Discord'}, status_code=400)
        except Exception as e:
            print(f"Auth Exception: {e}")
            return JSONResponse({'error': 'Internal Auth Error'}, status_code=500)

@app.get('/api/auth/me')
async def get_me(request: Request):
    user = get_user_from_cookie(request)
    if user:
        # Don't send access_token to frontend
        return JSONResponse({
            'id': user['id'],
            'username': user['username'],
            'avatar': user['avatar'],
            'discriminator': user['discriminator'],
            'loggedIn': True
        })
    return JSONResponse({'loggedIn': False})

@app.post('/api/auth/logout')
async def logout():
    response = JSONResponse({'status': 'logged_out'})
    response.delete_cookie("chronix_session")
    return response

@app.get('/api/user/guilds')
async def get_user_guilds(request: Request):
    user = get_user_from_cookie(request)
    if not user or 'access_token' not in user:
         return JSONResponse({'error': 'Unauthorized'}, status_code=401)

    access_token = user['access_token']
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get('https://discord.com/api/users/@me/guilds', headers={
                'Authorization': f"Bearer {access_token}"
            })
            if r.status_code == 401:
                 # Token might be expired, simple handle: logout
                 resp = JSONResponse({'error': 'Token expired'}, status_code=401)
                 resp.delete_cookie("chronix_session")
                 return resp
                 
            r.raise_for_status()
            guilds = r.json()
            
            # TODO: In a real app, cross-reference with bot's guilds to check 'hasBot'
            # For this standalone, we'll mock the 'hasBot' check or just return raw guilds.
            # Let's just return raw and map it in frontend for now.
            return JSONResponse(guilds)
            
        except Exception as e:
             print(f"Guild fetch error: {e}")
             return JSONResponse({'error': 'Failed to fetch guilds'}, status_code=500)


@app.post('/rpc/consume')
async def _consume_handler(request: Request):
    api_key = os.environ.get('CHRONIX_DASHBOARD_API_KEY')
    
    # Security checks
    client_host = request.client.host if request.client else "unknown"
    local_hosts = ('127.0.0.1', '::1', 'localhost')
    if client_host not in local_hosts and api_key:
        key = request.headers.get('X-API-Key')
        if not key or key != api_key:
            return JSONResponse({'status': 'unauthorized'}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        data = None

    actions = None
    if isinstance(data, dict) and data.get('actions'):
        actions = data.get('actions')

    # Check for maintenance mode
    if os.getenv('CHRONIX_DASHBOARD_MAINTENANCE', 'false').lower() in ('true', '1', 'yes'):
        if actions:
            return JSONResponse({
                'status': 'error',
                'message': 'Maintenance mode active. Changes are not saved.'
            }, status_code=503)
            
    # In standalone mode, we can't dispatch directly to the bot's memory.
    # We MUST use the file-based trigger mechanism.
    if actions:
        # TODO: In a future enhancement, we could write actions to a queue file 
        # that the bot watches, but for now we'll just trigger a reload/consume event.
        print(f"Received standalone actions: {actions}")

    data_dir = Path(os.environ.get('CHRONIX_DATA_DIR', Path(__file__).parents[0] / 'data'))
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / 'dashboard_trigger').write_text(str(time.time()), encoding='utf-8')
    except Exception as e:
        print(f"Failed to write trigger file: {e}")
        
    return JSONResponse({'status': 'ok'})

@app.get('/api/stats')
async def _get_stats():
    data_dir = Path(os.environ.get('CHRONIX_DATA_DIR', Path(__file__).parents[0] / 'data'))
    stats_file = data_dir / 'dashboard_stats.json'
    if stats_file.exists():
        try:
            content = json.loads(stats_file.read_text(encoding='utf-8'))
            return JSONResponse(content)
        except Exception:
            pass
    return JSONResponse({'server_count': 0, 'uptime': 0, 'extensions': 0, 'maintenance_mode': False})

# Serve Dashboard Static Files
dashboard_dist = Path(os.environ.get('CHRONIX_DASHBOARD_BUILD_DIR', Path(__file__).parents[0] / 'dashboard' / 'dist'))

if dashboard_dist.exists() and dashboard_dist.is_dir():
    # Mount assets
    assets_path = dashboard_dist / 'assets'
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    # Serve root files
    for root_file in ['favicon.ico', 'manifest.json', 'robots.txt', 'logo192.png', 'logo512.png']:
            if (dashboard_dist / root_file).exists():
                # capture variable in default arg
                @app.get(f"/{root_file}")
                async def _serve_root(rf=root_file): 
                    return FileResponse(dashboard_dist / rf)

    # SPA Catch-all (serves index.html for any other route)
    @app.get("/{full_path:path}")
    async def _serve_spa(full_path: str):
        return FileResponse(dashboard_dist / 'index.html')

    print(f"Serving dashboard from {dashboard_dist}")
else:
    print(f"Dashboard build not found at {dashboard_dist}. Run 'npm run build' in dashboard/ directory.")

if __name__ == "__main__":
    rpc_host = os.getenv('CHRONIX_DASHBOARD_RPC_HOST', '127.0.0.1')
    rpc_port = int(os.getenv('CHRONIX_DASHBOARD_RPC_PORT', '9091'))
    print(f"Starting standalone dashboard server on {rpc_host}:{rpc_port}")
    uvicorn.run(app, host=rpc_host, port=rpc_port, log_level="info")
