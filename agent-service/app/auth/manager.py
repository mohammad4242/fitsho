from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from ..schemas import AgentName, AuthState
from .base import AgentAuthAdapter, AuthCommand, ParsedAuthUpdate
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
_AUTH_CREDENTIAL_POLL_INTERVAL_SECONDS = 0.25
AuthCredentialMarker = tuple[int, int, int] | None
AuthCredentialMarkerReader = Callable[[Mapping[str, str]], AuthCredentialMarker]


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
        self._discarded_sessions: set[UUID] = set()
        self._lock = asyncio.Lock()
        for adapter in self.adapters.values():
            recover_saved_credentials = getattr(adapter, "recover_saved_credentials", None)
            if callable(recover_saved_credentials):
                try:
                    recover_saved_credentials(self.environment)
                except (OSError, TypeError, ValueError):
                    # A stale backup is best-effort recovery; the next status
                    # probe will still refuse to claim authentication if it is
                    # unavailable or malformed.
                    pass

    async def update_environment(self, environment: Mapping[str, str]) -> None:
        """Apply runtime environment changes to authentication started afterwards."""

        async with self._lock:
            self.environment = safe_auth_environment(environment)

    async def start(self, agent: AgentName, *, force_reauth: bool = False) -> AuthSessionView:
        if not isinstance(agent, AgentName):
            raise AuthManagerError(
                "auth_unavailable", 422, AuthSafeErrorMessage.UNAVAILABLE
            )
        stale_process: AuthProcess | None = None
        stale_session: AuthSession | None = None
        async with self._lock:
            active_id = self._active.get(agent)
            if active_id is not None:
                active_session = self._sessions.get(active_id)
                if active_session is not None and active_session.is_active:
                    if self._is_expired(active_session):
                        active_session.mark_terminal(AuthSessionStatus.EXPIRED)
                        stale_process = active_session.process
                        stale_session = active_session
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
            if not force_reauth:
                probe_auth_state = getattr(adapter, "probe_auth_state", None)
                if callable(probe_auth_state):
                    probed_state = await self._probe_auth_state(probe_auth_state)
                    if probed_state is AuthState.AUTHENTICATED:
                        if stale_session is not None:
                            self._restore_saved_credentials(adapter)
                        session = AuthSession(
                            session_id=uuid4(),
                            agent=agent,
                            expires_at=datetime.now(UTC) + timedelta(seconds=self.ttl_seconds),
                        )
                        session.mark_terminal(AuthSessionStatus.AUTHENTICATED)
                        self._sessions[session.session_id] = session
                        self._notify_state(session)
                        if stale_process is not None:
                            asyncio.create_task(stale_process.terminate())
                        return session.view()
            if stale_session is not None:
                self._restore_saved_credentials(adapter)
            try:
                self._backup_saved_credentials(adapter)
            except (OSError, TypeError, ValueError) as exc:
                raise AuthManagerError(
                    "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                ) from exc
            if force_reauth:
                clear_saved_credentials = getattr(adapter, "clear_saved_credentials", None)
                if not callable(clear_saved_credentials):
                    self._restore_saved_credentials(adapter)
                    raise AuthManagerError(
                        "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                    )
                try:
                    cast(Callable[[Mapping[str, str]], None], clear_saved_credentials)(
                        self.environment
                    )
                except (OSError, TypeError, ValueError) as exc:
                    self._restore_saved_credentials(adapter)
                    raise AuthManagerError(
                        "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                    ) from exc
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
            enter_scheduled = [False]

            async def on_output(text: str) -> None:
                async with self._lock:
                    parser_buffer[0] = (parser_buffer[0] + text)[-self.max_output_bytes :]
                    if not session.is_terminal:
                        update = ParsedAuthUpdate()
                        try:
                            update = adapter.parse_output(parser_buffer[0])
                            if update.authenticated and self._requires_saved_credentials(adapter):
                                # A zero-exit/login-success message is not
                                # enough for CLIs that replace their auth file
                                # during startup. Wait for process completion or
                                # a saved-credential marker before claiming it.
                                update = replace(update, authenticated=False)
                            session.apply_update(
                                update,
                                allowed_hosts=adapter.allowed_auth_hosts(),
                            )
                        except (ValidationError, ValueError, TypeError):
                            session.mark_terminal(
                                AuthSessionStatus.FAILED,
                                AuthSafeErrorMessage.FAILED.value,
                            )
                        process = process_holder[0]
                        if (
                            update.press_enter
                            and process is not None
                            and process.is_running
                            and not enter_scheduled[0]
                        ):
                            enter_scheduled[0] = True
                            asyncio.create_task(self._press_enter(session, process))
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
                self._restore_saved_credentials(adapter)
                return session.view()
            asyncio.create_task(self._monitor(session, adapter, process, parser_buffer))
            view = session.view()

        if stale_process is not None:
            await stale_process.terminate()
        return view

    async def _press_enter(self, session: AuthSession, process: AuthProcess) -> None:
        try:
            await process.press_enter()
        except AuthProcessError:
            async with self._lock:
                if session.is_active:
                    session.mark_terminal(
                        AuthSessionStatus.FAILED,
                        AuthSafeErrorMessage.UNAVAILABLE.value,
                    )
                    self._notify_state(session)
                    self._release_active(session)
            await process.terminate()
            adapter = self.adapters.get(session.agent)
            if adapter is not None:
                self._restore_saved_credentials(adapter)

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
            adapter = self.adapters.get(session.agent)
            if adapter is not None:
                self._restore_saved_credentials(adapter)
        return view

    async def cancel_active(self, agent: AgentName) -> bool:
        process: AuthProcess | None = None
        canceled = False
        adapter = self.adapters.get(agent)
        async with self._lock:
            active_id = self._active.get(agent)
            if active_id is None:
                return False
            session = self._sessions.get(active_id)
            if session is None or not session.is_active:
                del self._active[agent]
                return False
            process = session.process
            if self._is_expired(session):
                session.mark_terminal(AuthSessionStatus.EXPIRED)
                self._release_active(session)
            else:
                session.mark_terminal(AuthSessionStatus.CANCELED)
                self._release_active(session)
                canceled = True
        if process is not None:
            await self._terminate_auth_process(process)
        if adapter is not None:
            self._restore_saved_credentials(adapter)
        return canceled

    async def logout(self, agent: AgentName) -> None:
        if not isinstance(agent, AgentName):
            raise AuthManagerError(
                "auth_unavailable", 422, AuthSafeErrorMessage.UNAVAILABLE
            )
        adapter = self.adapters.get(agent)
        if adapter is None:
            raise AuthManagerError(
                "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
            )

        process: AuthProcess | None = None
        async with self._lock:
            active_id = self._active.get(agent)
            if active_id is not None:
                session = self._sessions.get(active_id)
                if session is not None and session.is_active:
                    session.mark_terminal(AuthSessionStatus.CANCELED)
                    self._release_active(session)
                    self._discarded_sessions.add(session.session_id)
                    process = session.process
                else:
                    self._active.pop(agent, None)

        if process is not None:
            await self._terminate_auth_process(process)

        clear_saved_credentials = getattr(adapter, "clear_saved_credentials", None)
        if not callable(clear_saved_credentials):
            raise AuthManagerError(
                "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
            )
        try:
            cast(Callable[[Mapping[str, str]], None], clear_saved_credentials)(
                self.environment
            )
            finalize_saved_credentials = getattr(adapter, "finalize_saved_credentials", None)
            if callable(finalize_saved_credentials):
                cast(Callable[[Mapping[str, str]], None], finalize_saved_credentials)(
                    self.environment
                )
        except (OSError, TypeError, ValueError) as exc:
            raise AuthManagerError(
                "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
            ) from exc
        self._notify_auth_state(agent, AuthState.UNAUTHENTICATED)

    async def submit_input(self, session_id: UUID, value: str) -> AuthSessionView:
        try:
            validated = AuthInputRequest(value=value)
        except ValidationError as exc:
            raise AuthManagerError(
                "auth_input_invalid", 422, AuthSafeErrorMessage.INVALID_INPUT
            ) from exc

        process: AuthProcess | None = None
        expired = False
        adapter: AgentAuthAdapter | None = None
        credential_checker: Callable[[Mapping[str, str]], bool] | None = None
        credential_marker_reader: AuthCredentialMarkerReader | None = None
        credential_marker_before: AuthCredentialMarker = None
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
                adapter = self.adapters.get(session.agent)
                if adapter is not None:
                    has_saved_credentials = getattr(adapter, "has_saved_credentials", None)
                    if callable(has_saved_credentials):
                        credential_checker = cast(
                            Callable[[Mapping[str, str]], bool], has_saved_credentials
                        )
                    saved_credentials_marker = getattr(adapter, "saved_credentials_marker", None)
                    if callable(saved_credentials_marker):
                        credential_marker_reader = cast(
                            AuthCredentialMarkerReader, saved_credentials_marker
                        )
                        try:
                            credential_marker_before = credential_marker_reader(self.environment)
                        except (OSError, TypeError, ValueError):
                            credential_marker_before = None
                session.mark_verifying()
        if expired:
            if process is not None:
                await process.terminate()
            if adapter is None:
                adapter = self.adapters.get(session.agent)
            if adapter is not None:
                self._restore_saved_credentials(adapter)
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
                await self._terminate_auth_process(process)
                if adapter is not None:
                    self._restore_saved_credentials(adapter)
                raise AuthManagerError(
                    "auth_unavailable", 503, AuthSafeErrorMessage.UNAVAILABLE
                ) from exc
            finally:
                del validated
            if credential_checker is not None or credential_marker_reader is not None:
                asyncio.create_task(
                    self._monitor_saved_credentials(
                        session,
                        process,
                        credential_checker,
                        credential_marker_reader,
                        credential_marker_before,
                    )
                )
        elif process is not None:
            await process.terminate()
            if adapter is not None:
                self._restore_saved_credentials(adapter)
            raise AuthManagerError(
                "auth_session_expired", 410, AuthSafeErrorMessage.EXPIRED
            )
        return await self.get(session_id)

    async def _monitor_saved_credentials(
        self,
        session: AuthSession,
        process: AuthProcess,
        credential_checker: Callable[[Mapping[str, str]], bool] | None,
        credential_marker_reader: AuthCredentialMarkerReader | None,
        credential_marker_before: AuthCredentialMarker,
    ) -> None:
        while process.is_running:
            async with self._lock:
                if not session.is_active or session.status is not AuthSessionStatus.VERIFYING:
                    return
                if self._is_expired(session):
                    session.mark_terminal(AuthSessionStatus.EXPIRED)
                    self._release_active(session)
                    expired = True
                else:
                    expired = False
            if expired:
                await self._terminate_auth_process(process)
                adapter = self.adapters.get(session.agent)
                if adapter is not None:
                    self._restore_saved_credentials(adapter)
                return

            if credential_marker_reader is not None:
                try:
                    credential_marker_after = credential_marker_reader(self.environment)
                except (OSError, TypeError, ValueError):
                    credential_marker_after = None
                marker_changed = (
                    credential_marker_after is not None
                    and credential_marker_after != credential_marker_before
                )
                if credential_checker is not None:
                    try:
                        credentials_ready = marker_changed and credential_checker(
                            self.environment
                        )
                    except (OSError, TypeError, ValueError):
                        credentials_ready = False
                else:
                    credentials_ready = marker_changed
            elif credential_checker is not None:
                try:
                    credentials_ready = credential_checker(self.environment)
                except (OSError, TypeError, ValueError):
                    credentials_ready = False
            else:
                credentials_ready = False
            if credentials_ready:
                should_terminate = False
                terminal_status: AuthSessionStatus | None = None
                async with self._lock:
                    if not session.is_active or session.status is not AuthSessionStatus.VERIFYING:
                        return
                    if self._is_expired(session):
                        session.mark_terminal(AuthSessionStatus.EXPIRED)
                        self._release_active(session)
                        should_terminate = True
                        terminal_status = AuthSessionStatus.EXPIRED
                    else:
                        session.mark_terminal(AuthSessionStatus.AUTHENTICATED)
                        self._notify_state(session)
                        self._release_active(session)
                        should_terminate = True
                        terminal_status = AuthSessionStatus.AUTHENTICATED
                if should_terminate:
                    await self._terminate_auth_process(process)
                    adapter = self.adapters.get(session.agent)
                    if adapter is not None and terminal_status is not None:
                        self._settle_saved_credentials(adapter, terminal_status)
                    return
            await asyncio.sleep(_AUTH_CREDENTIAL_POLL_INTERVAL_SECONDS)

    async def cancel(self, session_id: UUID) -> AuthSessionView:
        process: AuthProcess | None = None
        adapter: AgentAuthAdapter | None = None
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
                adapter = self.adapters.get(session.agent)
            view = session.view()
        if process is not None:
            await self._terminate_auth_process(process)
        if adapter is not None:
            self._restore_saved_credentials(adapter)
        return view

    @staticmethod
    async def _terminate_auth_process(process: AuthProcess) -> None:
        if process.command.use_pty and process.is_running:
            try:
                await process.press_escape()
                await asyncio.sleep(0.01)
            except AuthProcessError:
                pass
        await process.terminate()

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
        for session in sessions:
            adapter = self.adapters.get(session.agent)
            if adapter is not None:
                self._restore_saved_credentials(adapter)
        async with self._lock:
            self._sessions.clear()
            self._discarded_sessions.clear()

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
            self._restore_saved_credentials(adapter)
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
            self._restore_saved_credentials(adapter)
            return

        parser_buffer[0] = ""
        terminal_status: AuthSessionStatus | None = None
        async with self._lock:
            if session.is_terminal:
                terminal_status = session.status
            else:
                try:
                    status = adapter.classify_exit(result.returncode, result.final_text)
                except (ValueError, TypeError):
                    status = AuthSessionStatus.FAILED
                if result.output_truncated:
                    status = AuthSessionStatus.FAILED
                if (
                    status is AuthSessionStatus.AUTHENTICATED
                    and self._requires_saved_credentials(adapter)
                    and not self._has_saved_credentials(adapter)
                ):
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
                terminal_status = session.status
        if terminal_status is not None and session.session_id not in self._discarded_sessions:
            self._settle_saved_credentials(adapter, terminal_status)

    def _backup_saved_credentials(self, adapter: AgentAuthAdapter) -> None:
        backup_saved_credentials = getattr(adapter, "backup_saved_credentials", None)
        if callable(backup_saved_credentials):
            cast(Callable[[Mapping[str, str]], None], backup_saved_credentials)(
                self.environment
            )

    async def _probe_auth_state(self, probe: object) -> AuthState:
        try:
            result = cast(
                Callable[[Mapping[str, str]], AuthState | Awaitable[AuthState]], probe
            )(self.environment)
            if inspect.isawaitable(result):
                result = await result
            return result if isinstance(result, AuthState) else AuthState.UNKNOWN
        except (OSError, TypeError, ValueError, RuntimeError):
            return AuthState.UNKNOWN

    def _restore_saved_credentials(self, adapter: AgentAuthAdapter) -> None:
        restore_saved_credentials = getattr(adapter, "restore_saved_credentials", None)
        if not callable(restore_saved_credentials):
            return
        try:
            cast(Callable[[Mapping[str, str]], None], restore_saved_credentials)(
                self.environment
            )
        except (OSError, TypeError, ValueError):
            # Restoration is best effort; status remains failed/canceled and a
            # later probe will not claim authentication without the credential.
            pass

    def _settle_saved_credentials(
        self,
        adapter: AgentAuthAdapter,
        status: AuthSessionStatus,
    ) -> None:
        if status is AuthSessionStatus.AUTHENTICATED:
            finalize_saved_credentials = getattr(adapter, "finalize_saved_credentials", None)
            if callable(finalize_saved_credentials):
                try:
                    cast(Callable[[Mapping[str, str]], None], finalize_saved_credentials)(
                        self.environment
                    )
                except (OSError, TypeError, ValueError):
                    pass
            return
        self._restore_saved_credentials(adapter)

    def _requires_saved_credentials(self, adapter: AgentAuthAdapter) -> bool:
        return callable(getattr(adapter, "has_saved_credentials", None)) or callable(
            getattr(adapter, "saved_credentials_marker", None)
        )

    def _has_saved_credentials(self, adapter: AgentAuthAdapter) -> bool:
        has_saved_credentials = getattr(adapter, "has_saved_credentials", None)
        if callable(has_saved_credentials):
            try:
                return bool(
                    cast(Callable[[Mapping[str, str]], bool], has_saved_credentials)(
                        self.environment
                    )
                )
            except (OSError, TypeError, ValueError):
                return False
        saved_credentials_marker = getattr(adapter, "saved_credentials_marker", None)
        if callable(saved_credentials_marker):
            try:
                return (
                    cast(AuthCredentialMarkerReader, saved_credentials_marker)(
                        self.environment
                    )
                    is not None
                )
            except (OSError, TypeError, ValueError):
                return False
        return True

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
            self._notify_auth_state(session.agent, state)

    def _notify_auth_state(self, agent: AgentName, state: AuthState) -> None:
        if self.state_callback is not None:
            self.state_callback(agent, state)
