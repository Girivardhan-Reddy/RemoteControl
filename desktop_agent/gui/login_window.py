"""Login, registration, and first-run setup pages."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from auth import AuthClient
from gui.app_settings import GuiSettings, SettingsStore
from gui.workers import FunctionWorker


class LoginPage(QWidget):
    """Email/password login page."""

    logged_in = Signal(dict)
    show_register = Signal()
    notify = Signal(str)

    def __init__(self, auth_client: AuthClient, settings: GuiSettings) -> None:
        super().__init__()
        self.auth_client = auth_client
        self.settings = settings
        self.pool = QThreadPool.globalInstance()
        self.backend_url = QLineEdit(settings.backend_url)
        self.backend_url.setPlaceholderText("Backend URL")
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.remember = QCheckBox("Remember me")
        self.remember.setChecked(settings.remember_me)
        self.login_button = QPushButton("Login")
        self.register_button = QPushButton("Create Account")
        self.forgot_button = QPushButton("Forgot Password")
        self.error = QLabel("")
        self.error.setObjectName("Muted")
        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.hide()
        self._build()
        self.login_button.clicked.connect(self.login)
        self.register_button.clicked.connect(self.show_register.emit)
        self.forgot_button.clicked.connect(lambda: self.notify.emit("Password reset is handled by the account administrator."))

    def _build(self) -> None:
        card = QFrame()
        card.setObjectName("Panel")
        card.setMaximumWidth(460)
        layout = QVBoxLayout(card)
        title = QLabel("Remote Control Agent")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Sign in to connect this computer to your backend.")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(16)
        layout.addWidget(self.backend_url)
        layout.addWidget(self.email)
        layout.addWidget(self.password)
        layout.addWidget(self.remember)
        layout.addWidget(self.loading)
        layout.addWidget(self.error)
        layout.addWidget(self.login_button)
        layout.addWidget(self.register_button)
        layout.addWidget(self.forgot_button)
        root = QHBoxLayout(self)
        root.addStretch()
        root.addWidget(card)
        root.addStretch()

    def login(self) -> None:
        """Run login in a worker thread."""
        self.error.clear()
        self.settings.backend_url = self.backend_url.text().strip().rstrip("/")
        SettingsStore().save(self.settings)
        self.auth_client.config = self.settings.to_agent_config()
        self.loading.show()
        self.login_button.setEnabled(False)
        worker = FunctionWorker(self.auth_client.login, self.email.text().strip(), self.password.text())
        worker.signals.result.connect(self._login_success)
        worker.signals.error.connect(self._login_error)
        worker.signals.finished.connect(lambda: self.login_button.setEnabled(True))
        self.pool.start(worker)

    def _login_success(self, result: object) -> None:
        self.loading.hide()
        SettingsStore().save(self.settings)
        self.notify.emit("Login successful.")
        self.logged_in.emit(result if isinstance(result, dict) else {})

    def _login_error(self, message: str) -> None:
        self.loading.hide()
        self.error.setText(message)
        self.notify.emit("Login failed.")


class RegisterPage(QWidget):
    """Registration page using the backend register endpoint."""

    registered = Signal(dict)
    show_login = Signal()
    notify = Signal(str)

    def __init__(self, auth_client: AuthClient) -> None:
        super().__init__()
        self.auth_client = auth_client
        self.pool = QThreadPool.globalInstance()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name")
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("Confirm password")
        self.confirm.setEchoMode(QLineEdit.Password)
        self.strength = QProgressBar()
        self.strength.setRange(0, 100)
        self.error = QLabel("")
        self.error.setObjectName("Muted")
        self.register_button = QPushButton("Register")
        self.back_button = QPushButton("Back to Login")
        self._build()
        self.password.textChanged.connect(self._update_strength)
        self.register_button.clicked.connect(self.register)
        self.back_button.clicked.connect(self.show_login.emit)

    def _build(self) -> None:
        card = QFrame()
        card.setObjectName("Panel")
        card.setMaximumWidth(460)
        layout = QVBoxLayout(card)
        title = QLabel("Create Account")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        for widget in (self.name, self.email, self.password, self.confirm, self.strength, self.error, self.register_button, self.back_button):
            layout.addWidget(widget)
        root = QHBoxLayout(self)
        root.addStretch()
        root.addWidget(card)
        root.addStretch()

    def _update_strength(self, password: str) -> None:
        score = 0
        score += min(len(password) * 5, 40)
        score += 20 if any(ch.isupper() for ch in password) else 0
        score += 20 if any(ch.islower() for ch in password) else 0
        score += 20 if any(ch.isdigit() for ch in password) else 0
        self.strength.setValue(min(score, 100))

    def register(self) -> None:
        """Register an account."""
        if self.password.text() != self.confirm.text():
            self.error.setText("Passwords do not match.")
            return
        payload = {
            "name": self.name.text().strip(),
            "email": self.email.text().strip(),
            "password": self.password.text(),
        }
        self.register_button.setEnabled(False)
        worker = FunctionWorker(lambda: self.auth_client._request("POST", "/auth/register", json=payload, retry_refresh=False).json())
        worker.signals.result.connect(self._registered)
        worker.signals.error.connect(self._error)
        worker.signals.finished.connect(lambda: self.register_button.setEnabled(True))
        self.pool.start(worker)

    def _registered(self, result: object) -> None:
        if isinstance(result, dict):
            self.auth_client.save_tokens(result)
            self.notify.emit("Registration successful.")
            self.registered.emit(result)

    def _error(self, message: str) -> None:
        self.error.setText(message)
        self.notify.emit("Registration failed.")


class SetupWizard(QWidget):
    """First-run setup wizard."""

    completed = Signal()
    notify = Signal(str)

    def __init__(self, settings: GuiSettings, auth_client: AuthClient) -> None:
        super().__init__()
        self.settings = settings
        self.auth_client = auth_client
        self.stack = QStackedWidget()
        self.backend_url = QLineEdit(settings.backend_url)
        self.device_label = QLabel("Device is not registered yet.")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("First Run Setup")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addWidget(self.stack)
        self.stack.addWidget(self._step_backend())
        self.stack.addWidget(self._step_login())
        self.stack.addWidget(self._step_device())
        self.stack.addWidget(self._step_done())

    def _step_backend(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Step 1: Enter Backend URL"))
        layout.addWidget(self.backend_url)
        next_button = QPushButton("Continue")
        layout.addWidget(next_button, alignment=Qt.AlignRight)
        next_button.clicked.connect(self._save_backend)
        return page

    def _step_login(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Step 2: Login from the Login page, then return here."))
        next_button = QPushButton("I am logged in")
        layout.addWidget(next_button, alignment=Qt.AlignRight)
        next_button.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        return page

    def _step_device(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Step 3: Register this device"))
        layout.addWidget(self.device_label)
        register = QPushButton("Register Device")
        layout.addWidget(register)
        register.clicked.connect(self._register_device)
        return page

    def _step_done(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Step 4: Complete"))
        finish = QPushButton("Open Dashboard")
        layout.addWidget(finish)
        finish.clicked.connect(self.completed.emit)
        return page

    def _save_backend(self) -> None:
        self.settings.backend_url = self.backend_url.text().strip().rstrip("/")
        SettingsStore().save(self.settings)
        self.notify.emit("Backend URL saved.")
        self.stack.setCurrentIndex(1)

    def _register_device(self) -> None:
        try:
            device = self.auth_client.register_device()
            self.device_label.setText(f"Device registered: {device.get('id')}\nPairing code: {device.get('pairing_code', 'Already paired')}")
            self.notify.emit("Device registered.")
            self.stack.setCurrentIndex(3)
        except Exception as exc:
            self.device_label.setText(str(exc))
            self.notify.emit("Device registration failed.")
