"""Account gateway. Each user gets a separate DB, repository root and artifact directory."""
import asyncio
import os
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .accounts import Accounts, Credentials
from .store import Store


def create_account_app(client=None, reasoner=None, runbooks=None, monitor=True):
    from .main import create_workspace_app
    root = Path(os.getenv('DATA_DIR', './data')).resolve()
    accounts = Accounts(root)
    accounts.seed()
    workspaces = {}
    stack, lock = AsyncExitStack(), asyncio.Lock()

    async def workspace(user):
        key = 'operator' if user['role'] == 'admin' else user['id']
        async with lock:
            if key not in workspaces:
                directory = root / 'workspaces' / key
                directory.mkdir(parents=True, exist_ok=True)
                app = create_workspace_app(
                    store=Store(os.getenv('DATABASE_URL', 'sqlite:///./ctrlz.db') if key == 'operator' else f'sqlite:///{directory / "workspace.db"}'),
                    client=client, reasoner=reasoner, runbooks=runbooks, monitor=monitor,
                    workspace_root=None if key == 'operator' else directory)
                await stack.enter_async_context(app.router.lifespan_context(app))
                workspaces[key] = app
            return workspaces[key]

    @asynccontextmanager
    async def lifespan(app):
        # Resume monitoring even before users open a browser after a restart.
        for user in accounts.users():
            await workspace(user)
        yield
        await stack.aclose()

    app = FastAPI(title='CtrlZ accounts and recovery', lifespan=lifespan)
    app.state.accounts = accounts
    origins = [s.strip() for s in os.getenv('CTRLZ_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if s.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST','PUT'], allow_headers=['Content-Type','Authorization','X-Operator-Token','Last-Event-ID'])

    def token(request):
        bearer = request.headers.get('authorization', '')
        return bearer[7:] if bearer.startswith('Bearer ') else request.headers.get('x-operator-token', '')

    def principal(request: Request):
        return accounts.resolve(token(request))

    def admin(user=Depends(principal)):
        if user['role'] != 'admin':
            raise HTTPException(403, 'Administrator access required')
        return user

    @app.get('/auth/config')
    def config():
        return {'registration_enabled': os.getenv('CTRLZ_ALLOW_REGISTRATION','true').lower() == 'true'}

    @app.post('/auth/login')
    def login(body: Credentials, request: Request):
        accounts.throttle('login-ip:'+str(request.client.host if request.client else 'unknown'), 50)
        accounts.throttle('login-email:'+body.email)
        return accounts.login(body)

    @app.post('/auth/register', status_code=201)
    async def register(body: Credentials, request: Request):
        if not config()['registration_enabled']:
            raise HTTPException(403, 'Registration is invite-only. Contact an administrator')
        accounts.throttle('register:'+str(request.client.host if request.client else 'unknown'), 5)
        user = accounts.create(body)
        await workspace(user)
        return accounts.login(body)

    @app.get('/auth/me')
    def me(user=Depends(principal)):
        return user

    @app.post('/auth/logout')
    def logout(request: Request, user=Depends(principal)):
        accounts.logout(token(request))
        return {'signed_out': True}

    class PasswordChange(BaseModel):
        current_password: str = Field(min_length=12, max_length=128)
        password: str = Field(min_length=12, max_length=128)

    @app.post('/auth/password')
    def password(body: PasswordChange, user=Depends(principal)):
        accounts.throttle('password:'+user['id'])
        session = accounts.login(Credentials(email=user['email'], password=body.current_password))
        accounts.logout(session['token'])
        accounts.change_password(user, body.password)
        return {'signed_out': True}

    @app.get('/auth/users')
    def users(user=Depends(admin)):
        return accounts.users()

    @app.post('/auth/users', status_code=201)
    async def invite(body: Credentials, user=Depends(admin)):
        created = accounts.create(body)  # API can never self-assign administrator privileges.
        await workspace(created)
        return created

    class Gateway:
        async def __call__(self, scope, receive, send):
            request = Request(scope)
            if scope['path'] == '/health':
                await JSONResponse({'status':'healthy','service':'ctrlz'})(scope, receive, send)
                return
            try:
                supplied = token(request)
                # Retain explicit local CLI access only when enabled by the deployer.
                import secrets
                expected = os.getenv('CTRLZ_OPERATOR_TOKEN','')
                if os.getenv('CTRLZ_ALLOW_OPERATOR_TOKEN','false').lower() == 'true' and expected and secrets.compare_digest(expected, supplied):
                    user = {'id':'operator','email':'local-operator','role':'admin'}
                else:
                    user = accounts.resolve(supplied)
                scope.setdefault('state', {})['principal'] = user
                if user['id'] != 'operator':
                    scope['state']['validate_session'] = lambda: accounts.resolve(supplied)
                target = await workspace(user)
                await target(scope, receive, send)
            except HTTPException as exc:
                await JSONResponse({'detail':exc.detail}, status_code=exc.status_code)(scope, receive, send)

    # Keep authenticated /health metadata; public health is intentionally minimal.
    @app.get('/health')
    async def health(request: Request):
        if token(request):
            user = principal(request)
            target = await workspace(user)
            return next(r.endpoint for r in target.routes if getattr(r,'path',None)=='/health')()
        return {'status':'healthy','service':'ctrlz'}

    app.mount('/', Gateway())
    return app
