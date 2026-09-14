import logging
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import runtime
from credentials_file import load_credentials

logger = logging.getLogger("monitoring-agent.gui")

APP_TITLE = "DevOps Monitor Pro — Monitoring Agent"


class AgentGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("560x420")
        self.root.minsize(520, 400)
        self.root.configure(bg="#0d1117")

        self.loop = None
        self._enrolling = False

        self._build_styles()
        self._build_ui()
        self._show_existing_credentials()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#0d1117")
        style.configure("Card.TFrame", background="#161b22")
        style.configure(
            "TLabel",
            background="#0d1117",
            foreground="#e6edf3",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Title.TLabel",
            background="#0d1117",
            foreground="#ffffff",
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#0d1117",
            foreground="#8b949e",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background="#161b22",
            foreground="#8b949e",
            font=("Segoe UI", 9),
            wraplength=480,
            justify="left",
        )
        style.configure("TEntry", fieldbackground="#0d1117", foreground="#e6edf3")
        style.configure(
            "Primary.TButton",
            background="#238636",
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padding=8,
        )
        style.map("Primary.TButton", background=[("active", "#2ea043")])
        style.configure(
            "Secondary.TButton",
            background="#21262d",
            foreground="#e6edf3",
            padding=6,
        )
        style.map("Secondary.TButton", background=[("active", "#30363d")])

    def _build_ui(self) -> None:
        header = ttk.Frame(self.root, style="TFrame")
        header.pack(fill="x", padx=24, pady=(20, 4))
        ttk.Label(header, text="DevOps Monitor Pro", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Monitoring Agent — connect this computer to your dashboard",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        card = ttk.Frame(self.root, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=24, pady=12)

        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        ttk.Label(
            inner,
            text="Enrollment code",
            style="TLabel",
            background="#161b22",
        ).pack(anchor="w", pady=(4, 2))
        self.code_entry = ttk.Entry(inner, show="●", font=("Consolas", 11), width=44)
        self.code_entry.pack(fill="x", pady=(0, 4), ipady=3)
        self.code_entry.focus_set()

        self.connect_btn = ttk.Button(
            inner, text="Connect Agent", style="Primary.TButton", command=self._on_connect
        )
        self.connect_btn.pack(anchor="w", pady=(6, 10))

        ttk.Label(inner, text="Status", style="TLabel", background="#161b22").pack(anchor="w")
        self.status_var = tk.StringVar(value="Enter your enrollment code and click Connect Agent.")
        ttk.Label(inner, textvariable=self.status_var, style="Status.TLabel").pack(
            fill="x", pady=(2, 10)
        )

        divider = ttk.Separator(inner, orient="horizontal")
        divider.pack(fill="x", pady=6)

        self.unenroll_btn = ttk.Button(
            inner,
            text="Disconnect this agent",
            style="Secondary.TButton",
            command=self._on_unenroll,
        )
        # Shown only after successful enrollment.
        self.unenroll_btn.pack_forget()

        footer = ttk.Frame(self.root, style="TFrame")
        footer.pack(fill="x", padx=24, pady=(0, 12))
        ttk.Label(
            footer,
            text="Tip: the enrollment code comes from the dashboard (Servers → Install Agent). "
                 "It is valid for 20 minutes and can be used once.",
            style="Subtitle.TLabel",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _show_existing_credentials(self) -> None:
        creds = load_credentials()
        if not creds:
            return
        self.status_var.set(
            "This agent is already enrolled and configured.\n"
            "Monitoring is running. You can disconnect it below."
        )
        self._show_enrolled_controls()
        # Start monitoring immediately when already enrolled (e.g. right after
        # the installer finishes, or when the client opens the agent again).
        self._start_loop(creds)

    def _show_enrolled_controls(self) -> None:
        self.unenroll_btn.pack(anchor="w", pady=(6, 2))

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _on_connect(self) -> None:
        if self._enrolling or self.loop is not None:
            return
        code = self.code_entry.get().strip().strip('"').strip("'")
        if not code:
            messagebox.showwarning(APP_TITLE, "Please paste your enrollment code first.")
            return

        self._enrolling = True
        self.connect_btn.state(["disabled"])
        self.status_var.set("Connecting...")

        def worker() -> None:
            try:
                config = runtime.enroll_agent(code, status_cb=self._set_status)
            except runtime.EnrollmentError as exc:
                self.root.after(0, lambda: self._enroll_failed(exc.message))
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected enrollment error")
                self.root.after(
                    0,
                    lambda: self._enroll_failed(
                        "Unexpected error during enrollment. Please try again."
                    ),
                )
                _ = exc
                return
            self.root.after(0, lambda: self._enroll_succeeded(config))

        threading.Thread(target=worker, daemon=True).start()

    def _enroll_failed(self, message: str) -> None:
        self._enrolling = False
        self.connect_btn.state(["!disabled"])
        self.status_var.set(message)
        messagebox.showerror(APP_TITLE, message)

    def _enroll_succeeded(self, config: dict) -> None:
        self._enrolling = False
        self.connect_btn.state(["!disabled"])
        self.code_entry.delete(0, tk.END)
        self._start_loop(config)
        self._show_enrolled_controls()
        self.root.after(2000, lambda: messagebox.showinfo(APP_TITLE, "Successfully connected."))

    def _start_loop(self, config: dict) -> None:
        if self.loop is not None:
            return
        self.loop = runtime.MonitoringLoop(
            server_id=config["server_id"],
            agent_token=config["agent_token"],
            api_url=config["api_url"],
            interval=config.get("interval_seconds", runtime.DEFAULT_INTERVAL_SECONDS),
            status_cb=lambda msg: self.root.after(0, lambda m=msg: self.status_var.set(m)),
        )
        self.loop.start()

    def _set_status(self, message: str) -> None:
        # Called from worker threads; marshal into the Tk main loop.
        try:
            self.root.after(0, lambda m=message: self.status_var.set(m))
        except tk.TclError:
            pass

    def _on_unenroll(self) -> None:
        if not messagebox.askyesno(
            APP_TITLE,
            "Disconnect this agent?\n\n"
            "Local credentials will be removed. Monitoring stops until you "
            "enroll again with a new code.",
        ):
            return
        if self.loop is not None:
            self.loop.stop()
            self.loop = None
        from credentials_file import clear_credentials

        clear_credentials()
        self.status_var.set("Agent disconnected. Enter a new enrollment code to reconnect.")
        self.unenroll_btn.pack_forget()

    def _on_close(self) -> None:
        if self.loop is not None:
            if not messagebox.askyesno(
                APP_TITLE,
                "Close the agent window?\n\n"
                "Monitoring stops when the window closes. Reopen the agent any "
                "time to continue monitoring.",
            ):
                return
            self.loop.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    app = AgentGUI()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
