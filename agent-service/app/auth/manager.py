from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from ..schemas import AgentName, AuthState
from .base import AgentAuthAdapter, AuthCommand
from .process import (
    AuthOutputCallback,
    AuthProcess,
    AuthProcessError,
    safe_auth_environment,
)
from .schemas import AuthInputRequest, AuthSafeErrorMessage, AuthSessionStatus, AuthSessionView
from .session import AuthSession


class AuthManagerError(RuntimeError):
    def __init__(self, code: str, status_code: int, message: AuthSafeErrorMessage) -> None:
        super().__init__(message.value)
        self.code = code
        self.status_code = status_code
        self.safe_message = message.value


class AuthProcessFactory(Protocol):
    def __call__(
        self,
        command: AuthCommand,
        *,
        workspace: Path,
        environment: Mapping[str, str],
        max_output_bytes: int,
        output_callback: AuthOutputCallback,
    ) -> AuthProcess: ...


AuthStateCallback = Callable[[AgentName, AuthState], None]


class AuthManager:
    def __init__(
        self,
        adapters: Mapping[AgentName, AgentAuthAdapter],
        *,
        workspace: Path,
        ttl_seconds: float = 600,
        max_output_bytes: int = 65_536,
        environment: Mapping[str, str] | None = None,
        process_factory: AuthProcessFactory | None = None,
        state_callback: AuthStateCallback | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self.adapters = dict(adapters)
        self.workspace = workspace
        self.ttl_seconds = ttl_seconds
        self.max_output_bytes = max_output_bytes
        self.environment = safe_auth_environment(environment)
        self.process_factory = process_factory or AuthProcess
        self.state_callback = state_callback
        self._sessions: dict[UUID, AuthSession] = {}
        self._active: dict[AgentName, UUID] = {}
        self._lock = asyncio.Lock()

    async def start(self, agent: AgentName) -> AuthSessionView:
        if not isinstance(agent, AgentName):
            raise AuthManagerError(
                "auth_unavailable", 422, AuthSafeErrorMessage.UNAVAILABLE
            )
        stale_process: AuthProcess | None = None
        async with self._lock:
            active_id = self._active.get(agent)
            if active_id is not None:
                active_session = self._sessions.get(active_id)
                if active_session is not None and active_session.is_active:
                    if self._is_expired(active_session):
                        active_session.mark_terminal(AuthSessionStatus.EXPIRED)
                        stale_process = active_session.process
                        del self._active[agent]
                    else:
                        raise AuthManagerError(
                            "auth_in_progress", 409, AuthSafeErrorMessage.IN_PROGRESS
                        )
                else:
                    del self._active[agent]

            adapter = self.adapters.get(agent)
            if adapter is None:
                raise AuthManagerError(
                    "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                )
            if adapter.manual_auth_only:
                raise AuthManagerError(
                    "auth_manual_only", 409, AuthSafeErrorMessage.UNAVAILABLE
                )
            session = AuthSession(
                session_id=uuid4(),
                agent=agent,
                expires_at=datetime.now(UTC) + timedelta(seconds=self.ttl_seconds),
            )
            self._sessions[session.session_id] = session
            self._active[agent] = session.session_id

            parser_buffer = [""]
            process_holder: list[AuthProcess | None] = [None]
            termination_scheduled = [False]

            async def on_output(text: str) -> None:
                async with self._lock:
                    parser_buffer[0] = (parser_buffer[0] + text)[-self.max_output_bytes :]
                    if not session.is_terminal:
                        try:
                            update = adapter.parse_output(parser_buffer[0])
                            session.apply_update(
                                update,
                                allowed_hosts=adapter.allowed_auth_hosts(),
                            )
                        except (ValidationError, ValueError, TypeError):
                            session.mark_terminal(
                                AuthSessionStatus.FAILED,
                                AuthSafeErrorMessage.FAILED.value,
                            )
                        if session.is_terminal:
                            self._notify_state(session)
                            self._release_active(session)
                    process = process_holder[0]
                    if session.is_terminal and process is not None and process.is_running:
                        if not termination_scheduled[0]:
                            termination_scheduled[0] = True
                            asyncio.create_task(process.terminate())

            try:
                process = self.process_factory(
                    adapter.command(),
                    workspace=self.workspace,
                    environment=self.environment,
                    max_output_bytes=self.max_output_bytes,
                    output_callback=on_output,
                )
                session.process = process
                process_holder[0] = process
                await process.start()
            except (AuthProcessError, OSError, ValueError):
                session.mark_terminal(
                    AuthSessionStatus.FAILED,
                    AuthSafeErrorMessage.UNAVAILABLE.value,
                )
                self._notify_state(session)
                del self._active[agent]
                return session.view()
            asyncio.create_task(self._monitor(session, adapter, process, parser_buffer))
            view = session.view()

        if stale_process is not None:
            await stale_process.terminate()
        return view

    async def get(self, session_id: UUID) -> AuthSessionView:
        process: AuthProcess | None = None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise AuthManagerError(
                    "auth_session_not_found", 404, AuthSafeErrorMessage.NOT_FOUND
                )
            if session.is_active and self._is_expired(session):
                session.mark_terminal(AuthSessionStatus.EXPIRED)
                self._release_active(session)
                process = session.process
            view = session.view()
        if process is not None:
            await process.terminate()
        return view

    async def submit_input(self, session_id: UUID, value: str) -> AuthSessionView:
        try:
            validated = AuthInputRequest(value=value)
        except ValidationError as exc:
            raise AuthManagerError(
                "auth_input_invalid", 422, AuthSafeErrorMessage.INVALID_INPUT
            ) from exc

        process: AuthProcess | None = None
        expired = False
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise AuthManagerError(
                    "auth_session_not_found", 404, AuthSafeErrorMessage.NOT_FOUND
                )
            if session.is_active and self._is_expired(session):
                session.mark_terminal(AuthSessionStatus.EXPIRED)
                self._release_active(session)
                process = session.process
                expired = True
            elif session.status is not AuthSessionStatus.WAITING_FOR_INPUT:
                raise AuthManagerError(
                    "auth_input_not_expected", 409, AuthSafeErrorMessage.INVALID_INPUT
                )
            else:
                process = session.process
                if process is None:
                    raise AuthManagerError(
                        "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                    )
                session.mark_verifying()
        if expired:
            if process is not None:
                await process.terminate()
            raise AuthManagerError(
                "auth_session_expired", 410, AuthSafeErrorMessage.EXPIRED
            )
        if process is not None and process.is_running:
            try:
                await process.send_input(validated.value)
            except AuthProcessError as exc:
                async with self._lock:
                    session = self._sessions.get(session_id)
                    if session is not None:
                        session.mark_terminal(
                            AuthSessionStatus.FAILED,
                            AuthSafeErrorMessage.UNAVAILABLE.value,
                        )
                        self._notify_state(session)
                        self._release_active(session)
                raise AuthManagerError(
                    "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                ) from exc
            finally:
                del validated
        elif process is not None:
            await process.terminate()
            raise AuthManagerError(
                "auth_session_expired", 410, AuthSafeErrorMessage.EXPIRED
            )
        return await self.get(session_id)

    async def cancel(self, session_id: UUID) -> AuthSessionView:
        process: AuthProcess | None = None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise AuthManagerError(
                    "auth_session_not_found", 404, AuthSafeErrorMessage.NOT_FOUND
                )
            if session.is_active:
                session.mark_terminal(AuthSessionStatus.CANCELED)
                self._release_active(session)
                process = session.process
            view = session.view()
        if process is not None:
            await process.terminate()
        return view

    async def shutdown(self) -> None:
        async with self._lock:
            sessions = [session for session in self._sessions.values() if session.is_active]
            for session in sessions:
                session.mark_terminal(AuthSessionStatus.CANCELED)
            self._active.clear()
            processes = [session.process for session in sessions if session.process is not None]
        await asyncio.gather(
            *(process.terminate() for process in processes),
            return_exceptions=True,
        )
        async with self._lock:
            self._sessions.clear()

    async def _monitor(
        self,
        session: AuthSession,
        adapter: AgentAuthAdapter,
        process: AuthProcess,
        parser_buffer: list[str],
    ) -> None:
        remaining = max(0.001, (session.expires_at - datetime.now(UTC)).total_seconds())
        try:
            result = await asyncio.wait_for(asyncio.shield(process.wait()), timeout=remaining)
        except TimeoutError:
            await process.terminate()
            async with self._lock:
                if session.is_active:
                    session.mark_terminal(AuthSessionStatus.EXPIRED)
                    self._release_active(session)
            parser_buffer[0] = ""
            return
        except (AuthProcessError, OSError):
            async with self._lock:
                if session.is_active:
                    session.mark_terminal(
                        AuthSessionStatus.FAILED,
                        AuthSafeErrorMessage.UNAVAILABLE.value,
                    )
                    self._notify_state(session)
                    self._release_active(session)
            parser_buffer[0] = ""
            return

        parser_buffer[0] = ""
        async with self._lock:
            if session.is_terminal:
                return
            try:
                status = adapter.classify_exit(result.returncode, result.final_text)
            except (ValueError, TypeError):
                status = AuthSessionStatus.FAILED
            if result.output_truncated:
                status = AuthSessionStatus.FAILED
            if status is AuthSessionStatus.AUTHENTICATED:
                session.mark_terminal(AuthSessionStatus.AUTHENTICATED)
            elif status is AuthSessionStatus.CANCELED:
                session.mark_terminal(AuthSessionStatus.CANCELED)
            else:
                session.mark_terminal(
                    AuthSessionStatus.FAILED,
                    AuthSafeErrorMessage.FAILED.value,
                )
            self._notify_state(session)
            self._release_active(session)

    @staticmethod
    def _is_expired(session: AuthSession) -> bool:
        return datetime.now(UTC) >= session.expires_at

    def _release_active(self, session: AuthSession) -> None:
        if self._active.get(session.agent) == session.session_id:
            del self._active[session.agent]

    def _notify_state(self, session: AuthSession) -> None:
        if self.state_callback is None:
            return
        state = {
            AuthSessionStatus.AUTHENTICATED: AuthState.AUTHENTICATED,
            AuthSessionStatus.FAILED: AuthState.UNAUTHENTICATED,
        }.get(session.status)
        if state is not None:
            self.state_callback(session.agent, state)
