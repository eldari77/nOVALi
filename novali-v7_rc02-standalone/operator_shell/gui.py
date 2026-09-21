from __future__ import annotations

import json
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from .acceptance import (
    build_manual_acceptance_evidence,
    write_manual_acceptance_report,
)
from .gui_presenter import (
    build_default_operator_gui_profile,
    build_launch_readiness,
    build_launch_refusal_summary,
    build_launch_result_summary,
    inspect_directive_wrapper,
    load_operator_gui_profile,
    operator_gui_profile_path,
    render_constraints_summary,
    render_dashboard_summary,
    render_launch_readiness,
    render_trusted_sources_summary,
    save_operator_gui_profile,
    stable_runtime_constraints_signature,
    summarize_trusted_source_rows,
)
from .launcher import (
    OperatorLaunchRefusedError,
    build_operator_dashboard_snapshot,
    launch_novali_main,
)
from .envelope import (
    BACKEND_LOCAL_DOCKER,
    BACKEND_LOCAL_GUARDED,
    build_default_operator_runtime_envelope_spec,
    operator_runtime_envelope_spec_path,
    validate_operator_runtime_envelope_spec,
)
from .policy import (
    build_default_runtime_constraints,
    default_operator_root,
    initialize_operator_policy_files,
    load_runtime_envelope_spec_or_default,
    load_runtime_constraints_or_default,
    load_trusted_source_bindings_or_default,
    load_trusted_source_secrets_or_default,
    read_operator_status_snapshot,
    save_runtime_envelope_spec,
    save_runtime_constraints,
    save_trusted_source_bindings,
    save_trusted_source_secrets,
    operator_runtime_constraints_path,
    validate_runtime_constraints,
    validate_trusted_source_bindings,
)


def _pretty(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


class OperatorShellApp(tk.Tk):
    def __init__(self, *, package_root: str | Path | None = None, operator_root: str | Path | None = None) -> None:
        super().__init__()
        self.package_root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
        self.operator_root = Path(operator_root) if operator_root is not None else default_operator_root()
        initialize_operator_policy_files(root=self.operator_root, package_root=self.package_root)

        profile_defaults = build_default_operator_gui_profile(self.package_root)
        self.operator_profile = load_operator_gui_profile(root=self.operator_root, package_root=self.package_root)

        self.title("NOVALI Operator Shell")
        self.geometry("1180x860")

        self.directive_file_var = tk.StringVar(
            value=str(self.operator_profile.get("recent_directive_file", profile_defaults["recent_directive_file"]))
        )
        self.state_root_var = tk.StringVar(
            value=str(self.operator_profile.get("recent_state_root", profile_defaults["recent_state_root"]))
        )
        self.resume_mode_var = tk.StringVar(
            value=str(self.operator_profile.get("recent_resume_mode", profile_defaults["recent_resume_mode"]))
        )
        self.launch_action_var = tk.StringVar(
            value=str(self.operator_profile.get("recent_launch_action", profile_defaults["recent_launch_action"]))
        )
        self.show_raw_status_var = tk.BooleanVar(
            value=bool(
                dict(self.operator_profile.get("display_preferences", {})).get(
                    "show_raw_json_sections",
                    dict(profile_defaults.get("display_preferences", {})).get("show_raw_json_sections", False),
                )
            )
        )
        self.directive_validation_var = tk.StringVar(value="No validation run yet.")
        self.launch_status_var = tk.StringVar(value="Idle")
        self.launch_readiness_var = tk.StringVar(value="Checking launch readiness...")
        self.constraints_status_var = tk.StringVar(value="Runtime constraints not yet validated.")
        self.runtime_backend_status_var = tk.StringVar(value="Runtime backend not yet inspected.")
        self.binding_status_var = tk.StringVar(value="No trusted source selected.")
        self.binding_secret_source_var = tk.StringVar(value="Secret source not yet inspected.")
        self.profile_status_var = tk.StringVar(
            value=f"Operator profile: {operator_gui_profile_path(self.operator_root)}"
        )
        self._current_binding_index = 0
        self._trusted_source_rows: list[dict[str, Any]] = []
        self._operator_status_snapshot: dict[str, Any] = {}
        self._directive_summary: dict[str, Any] = {}

        self.runtime_constraints_payload = load_runtime_constraints_or_default(
            root=self.operator_root,
            package_root=self.package_root,
        )
        self.runtime_envelope_payload = load_runtime_envelope_spec_or_default(
            root=self.operator_root,
            package_root=self.package_root,
        )
        self.binding_payload = load_trusted_source_bindings_or_default(
            root=self.operator_root,
            package_root=self.package_root,
        )
        self.secrets_payload = load_trusted_source_secrets_or_default(root=self.operator_root)
        self._saved_runtime_policy_signature = ""

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.directive_tab = ttk.Frame(notebook)
        self.trusted_sources_tab = ttk.Frame(notebook)
        self.constraints_tab = ttk.Frame(notebook)
        self.launch_tab = ttk.Frame(notebook)
        self.status_tab = ttk.Frame(notebook)
        notebook.add(self.directive_tab, text="Directive")
        notebook.add(self.trusted_sources_tab, text="Trusted Sources")
        notebook.add(self.constraints_tab, text="Runtime Constraints")
        notebook.add(self.launch_tab, text="Bootstrap / Launch")
        notebook.add(self.status_tab, text="Status Dashboard")

        self._build_directive_tab()
        self._build_trusted_sources_tab()
        self._build_constraints_tab()
        self._build_launch_tab()
        self._build_status_tab()
        self._bind_variable_traces()

        self._load_constraints_into_form()
        self._refresh_operator_status_snapshot()
        self._update_directive_validation()
        self._refresh_trusted_sources_tree()
        self._load_binding_into_form(0)
        self._refresh_constraints_summary_from_snapshot()
        self._refresh_status_dashboard()
        self._update_launch_readiness()

    def _bind_variable_traces(self) -> None:
        for variable in (
            self.directive_file_var,
            self.state_root_var,
            self.resume_mode_var,
            self.launch_action_var,
        ):
            variable.trace_add("write", self._on_profile_or_launch_context_changed)
        self.show_raw_status_var.trace_add("write", self._on_status_preference_changed)

    def _on_profile_or_launch_context_changed(self, *_args: Any) -> None:
        self._persist_operator_profile()
        self._update_directive_validation()
        self._update_launch_readiness()

    def _on_status_preference_changed(self, *_args: Any) -> None:
        self._persist_operator_profile()
        self._refresh_status_dashboard()

    def _persist_operator_profile(self) -> None:
        recent_sources = [
            row["source_id"]
            for row in self._trusted_source_rows[:8]
            if row.get("source_id")
        ]
        self.operator_profile = save_operator_gui_profile(
            {
                "recent_directive_file": str(self.directive_file_var.get().strip()),
                "recent_state_root": str(self.state_root_var.get().strip()),
                "recent_resume_mode": str(self.resume_mode_var.get().strip()),
                "recent_launch_action": str(self.launch_action_var.get().strip()),
                "recent_trusted_source_ids": recent_sources,
                "display_preferences": {
                    "show_raw_json_sections": bool(self.show_raw_status_var.get()),
                },
            },
            root=self.operator_root,
            package_root=self.package_root,
        )
        self.profile_status_var.set(f"Operator profile: {operator_gui_profile_path(self.operator_root)}")

    def _refresh_operator_status_snapshot(self) -> None:
        self._operator_status_snapshot = read_operator_status_snapshot(
            root=self.operator_root,
            package_root=self.package_root,
        )

    def _build_directive_tab(self) -> None:
        frame = self.directive_tab
        ttk.Label(frame, text="Directive File").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(frame, textvariable=self.directive_file_var, width=90).grid(
            row=0, column=1, sticky="ew", padx=8, pady=8
        )
        ttk.Button(frame, text="Browse", command=self._browse_directive_file).grid(
            row=0, column=2, padx=8, pady=8
        )

        ttk.Label(frame, text="State Root").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(frame, textvariable=self.state_root_var, width=90).grid(
            row=1, column=1, sticky="ew", padx=8, pady=8
        )
        ttk.Button(frame, text="Browse", command=self._browse_state_root).grid(
            row=1, column=2, padx=8, pady=8
        )

        ttk.Label(frame, text="Startup Mode").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=2, column=1, sticky="w", padx=8, pady=8)
        ttk.Radiobutton(
            mode_frame,
            text="New Bootstrap",
            value="new_bootstrap",
            variable=self.resume_mode_var,
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            mode_frame,
            text="Resume Existing State",
            value="resume_existing",
            variable=self.resume_mode_var,
        ).pack(side="left", padx=4)
        ttk.Button(frame, text="Validate Wrapper", command=self._validate_directive_wrapper).grid(
            row=2, column=2, padx=8, pady=8
        )

        ttk.Label(
            frame,
            textvariable=self.directive_validation_var,
            wraplength=940,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        ttk.Label(
            frame,
            text=(
                "Directive selection is operator input only. Canonical startup authority still comes from "
                "directive-first bootstrap plus persisted governance artifacts."
            ),
            wraplength=940,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        ttk.Label(
            frame,
            text=(
                "Need a formal directive file? Use DIRECTIVE_AUTHORING_GUIDE.md or the scaffold helper "
                "`standalone_docker/generate_directive_scaffold.ps1` before activation."
            ),
            wraplength=940,
            justify="left",
        ).grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        ttk.Label(
            frame,
            textvariable=self.profile_status_var,
            wraplength=940,
            justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))
        frame.columnconfigure(1, weight=1)

    def _build_trusted_sources_tab(self) -> None:
        frame = self.trusted_sources_tab
        columns = ("source_id", "enabled", "kind", "strategy", "secret_source", "availability")
        self.sources_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        headings = {
            "source_id": ("Source", 220),
            "enabled": ("Enabled", 90),
            "kind": ("Kind", 130),
            "strategy": ("Credential", 120),
            "secret_source": ("Secret Source", 180),
            "availability": ("Availability", 180),
        }
        for column in columns:
            text, width = headings[column]
            self.sources_tree.heading(column, text=text)
            self.sources_tree.column(column, width=width, stretch=(column == "source_id"))
        self.sources_tree.bind("<<TreeviewSelect>>", self._on_binding_selected)
        self.sources_tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)

        self.binding_source_id_var = tk.StringVar()
        self.binding_source_kind_var = tk.StringVar()
        self.binding_enabled_var = tk.BooleanVar(value=False)
        self.binding_strategy_var = tk.StringVar(value="none")
        self.binding_credential_ref_var = tk.StringVar()
        self.binding_path_hint_var = tk.StringVar()
        self.binding_secret_value_var = tk.StringVar()

        detail = ttk.LabelFrame(frame, text="Selected Trusted Source")
        detail.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        ttk.Label(detail, text="Source ID").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(detail, textvariable=self.binding_source_id_var, state="readonly", width=54).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Label(detail, text="Source Kind").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(detail, textvariable=self.binding_source_kind_var, state="readonly", width=54).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Checkbutton(detail, text="Enabled", variable=self.binding_enabled_var).grid(
            row=2, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Label(detail, text="Credential Strategy").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(
            detail,
            textvariable=self.binding_strategy_var,
            values=("none", "env_var", "local_secret_store"),
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(detail, text="Credential Ref").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(detail, textvariable=self.binding_credential_ref_var).grid(
            row=4, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Label(detail, text="Path Hint").grid(row=5, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(detail, textvariable=self.binding_path_hint_var).grid(
            row=5, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Label(detail, text="Local Secret Value").grid(row=6, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(detail, textvariable=self.binding_secret_value_var, show="*").grid(
            row=6, column=1, sticky="ew", padx=6, pady=4
        )
        ttk.Label(
            detail,
            textvariable=self.binding_status_var,
            wraplength=480,
            justify="left",
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Label(
            detail,
            textvariable=self.binding_secret_source_var,
            wraplength=480,
            justify="left",
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Button(detail, text="Save Selected Binding", command=self._save_selected_binding).grid(
            row=9, column=0, padx=6, pady=8, sticky="w"
        )
        ttk.Button(detail, text="Test / Refresh Availability", command=self._refresh_trusted_sources_tree).grid(
            row=9, column=1, padx=6, pady=8, sticky="e"
        )
        detail.columnconfigure(1, weight=1)

        self.sources_summary_text = ScrolledText(frame, height=12)
        self.sources_summary_text.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

    def _build_constraints_tab(self) -> None:
        frame = self.constraints_tab
        self.constraint_vars = {
            "max_memory_mb": tk.StringVar(),
            "max_python_threads": tk.StringVar(),
            "max_child_processes": tk.StringVar(),
            "subprocess_mode": tk.StringVar(),
            "working_directory": tk.StringVar(),
            "allowed_write_roots": tk.StringVar(),
            "session_time_limit_seconds": tk.StringVar(),
        }
        self.envelope_vars = {
            "backend_kind": tk.StringVar(value=BACKEND_LOCAL_GUARDED),
            "cpu_limit_cpus": tk.StringVar(),
            "docker_image": tk.StringVar(value="python:3.12-slim"),
            "network_policy_intent": tk.StringVar(value="deny_all"),
        }
        row = 0
        for key, label in (
            ("max_memory_mb", "Max Memory (MB)"),
            ("max_python_threads", "Max Python Threads"),
            ("max_child_processes", "Max Child Processes"),
            ("subprocess_mode", "Subprocess Mode"),
            ("working_directory", "Working Directory"),
            ("allowed_write_roots", "Allowed Write Roots (; separated)"),
            ("session_time_limit_seconds", "Session Time Limit (s)"),
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=6)
            if key == "subprocess_mode":
                ttk.Combobox(
                    frame,
                    textvariable=self.constraint_vars[key],
                    values=("disabled", "bounded", "allow"),
                    state="readonly",
                ).grid(row=row, column=1, sticky="ew", padx=8, pady=6)
            else:
                ttk.Entry(frame, textvariable=self.constraint_vars[key], width=80).grid(
                    row=row, column=1, sticky="ew", padx=8, pady=6
                )
            row += 1
        ttk.Label(frame, text="Runtime Backend").grid(row=row, column=0, sticky="w", padx=8, pady=6)
        self.envelope_backend_combo = ttk.Combobox(
            frame,
            textvariable=self.envelope_vars["backend_kind"],
            values=(BACKEND_LOCAL_GUARDED, BACKEND_LOCAL_DOCKER),
            state="readonly",
        )
        self.envelope_backend_combo.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        row += 1
        ttk.Label(frame, text="Docker CPU Limit (cpus)").grid(row=row, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.envelope_vars["cpu_limit_cpus"], width=80).grid(
            row=row, column=1, sticky="ew", padx=8, pady=6
        )
        row += 1
        ttk.Label(frame, text="Docker Image").grid(row=row, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.envelope_vars["docker_image"], width=80).grid(
            row=row, column=1, sticky="ew", padx=8, pady=6
        )
        row += 1
        ttk.Label(frame, text="Network Policy Intent").grid(row=row, column=0, sticky="w", padx=8, pady=6)
        ttk.Combobox(
            frame,
            textvariable=self.envelope_vars["network_policy_intent"],
            values=("deny_all",),
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        row += 1
        ttk.Button(frame, text="Validate", command=self._validate_constraints).grid(
            row=row, column=0, padx=8, pady=8, sticky="w"
        )
        ttk.Button(frame, text="Save / Apply", command=self._save_constraints).grid(
            row=row, column=1, padx=8, pady=8, sticky="e"
        )
        row += 1
        ttk.Label(
            frame,
            text=(
                "Controls listed as unsupported remain visible for honesty and future backend-neutral planning, "
                "but they are not claimed as enforced in this local GUI slice."
            ),
            wraplength=940,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))
        row += 1
        ttk.Label(
            frame,
            textvariable=self.constraints_status_var,
            wraplength=940,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        row += 1
        ttk.Label(
            frame,
            textvariable=self.runtime_backend_status_var,
            wraplength=940,
            justify="left",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
        row += 1
        self.constraints_summary_text = ScrolledText(frame, height=20)
        self.constraints_summary_text.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row, weight=1)

    def _build_launch_tab(self) -> None:
        frame = self.launch_tab
        ttk.Label(frame, text="Launch Action").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Combobox(
            frame,
            textvariable=self.launch_action_var,
            values=("bootstrap_only", "governed_execution", "proposal_analytics", "proposal_recommend"),
            state="readonly",
        ).grid(row=0, column=1, sticky="w", padx=8, pady=8)
        self.launch_button = ttk.Button(frame, text="Initialize", command=self._launch_selected_action)
        self.launch_button.grid(row=0, column=2, padx=8, pady=8)
        ttk.Label(
            frame,
            textvariable=self.launch_readiness_var,
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        ttk.Label(
            frame,
            textvariable=self.launch_status_var,
            wraplength=980,
            justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        self.launch_output_text = ScrolledText(frame, height=28)
        self.launch_output_text.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

    def _build_status_tab(self) -> None:
        frame = self.status_tab
        controls = ttk.Frame(frame)
        controls.pack(fill="x", padx=8, pady=8)
        ttk.Button(controls, text="Refresh", command=self._refresh_status_dashboard).pack(
            side="left",
            padx=(0, 8),
        )
        ttk.Button(
            controls,
            text="Export Acceptance Snapshot",
            command=self._export_acceptance_snapshot,
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            controls,
            text="Show raw JSON below summary",
            variable=self.show_raw_status_var,
        ).pack(side="left")
        self.status_text = ScrolledText(frame)
        self.status_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _browse_directive_file(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(self.package_root),
            filetypes=[("JSON", "*.json")],
        )
        if path:
            self.directive_file_var.set(path)

    def _browse_state_root(self) -> None:
        path = filedialog.askdirectory(initialdir=str(self.package_root))
        if path:
            self.state_root_var.set(path)

    def _update_directive_validation(self) -> None:
        self._directive_summary = inspect_directive_wrapper(
            self.directive_file_var.get().strip(),
            resume_mode=self.resume_mode_var.get().strip(),
        )
        summary_text = str(self._directive_summary.get("summary", ""))
        details = list(self._directive_summary.get("details", []))
        if details:
            summary_text = "\n".join([summary_text, "", *[f"- {item}" for item in details]])
        self.directive_validation_var.set(summary_text)

    def _validate_directive_wrapper(self) -> None:
        self._update_directive_validation()
        if self._directive_summary.get("is_valid", False):
            messagebox.showinfo("Directive Validation", str(self._directive_summary.get("summary", "")))
        else:
            messagebox.showerror("Directive Validation", self.directive_validation_var.get())

    def _refresh_trusted_sources_tree(self) -> None:
        self._refresh_operator_status_snapshot()
        summary = summarize_trusted_source_rows(self._operator_status_snapshot)
        self._trusted_source_rows = list(summary["rows"])
        for item in self.sources_tree.get_children():
            self.sources_tree.delete(item)
        for index, row in enumerate(self._trusted_source_rows):
            self.sources_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row["source_id"],
                    row["enabled_label"],
                    row["source_kind"],
                    row["credential_strategy"],
                    row["secret_source_label"],
                    row["availability_class"],
                ),
            )
        self.sources_summary_text.delete("1.0", tk.END)
        self.sources_summary_text.insert("1.0", render_trusted_sources_summary(self._operator_status_snapshot))
        if self._trusted_source_rows:
            current_index = max(0, min(self._current_binding_index, len(self._trusted_source_rows) - 1))
            self.sources_tree.selection_set(str(current_index))
            self._load_binding_into_form(current_index)
        self._update_launch_readiness()

    def _on_binding_selected(self, _event: Any) -> None:
        selected = self.sources_tree.selection()
        if not selected:
            return
        self._load_binding_into_form(int(selected[0]))

    def _binding_status_row(self, source_id: str) -> dict[str, Any]:
        for row in self._trusted_source_rows:
            if str(row.get("source_id", "")) == str(source_id):
                return row
        return {}

    def _load_binding_into_form(self, index: int) -> None:
        bindings = list(self.binding_payload.get("bindings", []))
        if not bindings:
            self.binding_status_var.set("No trusted-source bindings are available.")
            self.binding_secret_source_var.set("Secret source not available.")
            return
        index = max(0, min(index, len(bindings) - 1))
        self._current_binding_index = index
        binding = dict(bindings[index])
        self.binding_source_id_var.set(str(binding.get("source_id", "")))
        self.binding_source_kind_var.set(str(binding.get("source_kind", "")))
        self.binding_enabled_var.set(bool(binding.get("enabled", False)))
        self.binding_strategy_var.set(str(binding.get("credential_strategy", "none")))
        self.binding_credential_ref_var.set(str(binding.get("credential_ref", "")))
        self.binding_path_hint_var.set(str(binding.get("path_hint", "")))
        secret_key = self.binding_credential_ref_var.get().strip() or self.binding_source_id_var.get().strip()
        secret_value = str(dict(self.secrets_payload.get("secrets_by_source", {})).get(secret_key, ""))
        self.binding_secret_value_var.set(secret_value)

        status_row = self._binding_status_row(self.binding_source_id_var.get().strip())
        if status_row:
            self.binding_status_var.set(
                "Availability: "
                f"{status_row.get('availability_class', '')} / "
                f"{status_row.get('availability_reason', '')}"
            )
            self.binding_secret_source_var.set(
                "Secret source: "
                f"{status_row.get('secret_source_label', '')}"
            )
        else:
            self.binding_status_var.set("Availability has not been inspected yet.")
            self.binding_secret_source_var.set("Secret source has not been inspected yet.")

    def _save_selected_binding(self) -> None:
        bindings = list(self.binding_payload.get("bindings", []))
        if not bindings:
            return
        binding = dict(bindings[self._current_binding_index])
        binding["enabled"] = bool(self.binding_enabled_var.get())
        binding["credential_strategy"] = str(self.binding_strategy_var.get())
        binding["credential_ref"] = str(self.binding_credential_ref_var.get().strip())
        binding["path_hint"] = str(self.binding_path_hint_var.get().strip())

        prospective_binding_payload = dict(self.binding_payload)
        prospective_bindings = list(bindings)
        prospective_bindings[self._current_binding_index] = binding
        prospective_binding_payload["bindings"] = prospective_bindings

        prospective_secrets_payload = dict(self.secrets_payload)
        secrets_by_source = dict(prospective_secrets_payload.get("secrets_by_source", {}))
        secret_key = binding["credential_ref"] or str(binding.get("source_id", ""))
        if str(self.binding_secret_value_var.get()).strip():
            secrets_by_source[secret_key] = str(self.binding_secret_value_var.get())
        elif secret_key in secrets_by_source:
            del secrets_by_source[secret_key]
        prospective_secrets_payload["secrets_by_source"] = secrets_by_source

        validation_errors, _, _ = validate_trusted_source_bindings(
            prospective_binding_payload,
            secrets_payload=prospective_secrets_payload,
        )
        selected_source_id = str(binding.get("source_id", ""))
        selected_errors = [
            item
            for item in validation_errors
            if selected_source_id in item or "schema_" in item
        ]
        if selected_errors:
            messagebox.showerror(
                "Trusted Sources",
                "\n".join([f"Cannot save binding for {selected_source_id}.", "", *[f"- {item}" for item in selected_errors]]),
            )
            return

        self.binding_payload["bindings"] = prospective_bindings
        save_trusted_source_bindings(self.binding_payload, root=self.operator_root)
        save_trusted_source_secrets(prospective_secrets_payload, root=self.operator_root)
        self.secrets_payload = prospective_secrets_payload
        self._persist_operator_profile()
        self._refresh_trusted_sources_tree()
        self._refresh_status_dashboard()
        messagebox.showinfo(
            "Trusted Sources",
            (
                "Trusted-source binding saved. Availability and secret-source status are refreshed conservatively "
                "from operator policy and current environment."
            ),
        )

    def _load_constraints_into_form(self) -> None:
        constraints = dict(self.runtime_constraints_payload.get("constraints", {}))
        self.constraint_vars["max_memory_mb"].set(str(constraints.get("max_memory_mb", "")))
        self.constraint_vars["max_python_threads"].set(str(constraints.get("max_python_threads", "")))
        self.constraint_vars["max_child_processes"].set(str(constraints.get("max_child_processes", "")))
        self.constraint_vars["subprocess_mode"].set(str(constraints.get("subprocess_mode", "disabled")))
        self.constraint_vars["working_directory"].set(str(constraints.get("working_directory", "")))
        self.constraint_vars["allowed_write_roots"].set(";".join(list(constraints.get("allowed_write_roots", []))))
        self.constraint_vars["session_time_limit_seconds"].set(str(constraints.get("session_time_limit_seconds", "")))
        envelope = dict(self.runtime_envelope_payload)
        intents = dict(envelope.get("constraint_intents", {}))
        docker_settings = dict(dict(envelope.get("backend_settings", {})).get(BACKEND_LOCAL_DOCKER, {}))
        self.envelope_vars["backend_kind"].set(str(envelope.get("backend_kind", BACKEND_LOCAL_GUARDED)))
        self.envelope_vars["cpu_limit_cpus"].set(
            "" if intents.get("cpu_limit_cpus") in {None, ""} else str(intents.get("cpu_limit_cpus"))
            if float(intents.get("cpu_limit_cpus", 0)).is_integer()
            else str(intents.get("cpu_limit_cpus"))
        )
        self.envelope_vars["docker_image"].set(str(docker_settings.get("image", "python:3.12-slim")))
        self.envelope_vars["network_policy_intent"].set(str(intents.get("network_policy_intent", "deny_all")))
        self._saved_runtime_policy_signature = self._runtime_policy_signature(
            self.runtime_constraints_payload,
            self.runtime_envelope_payload,
        )

    def _runtime_policy_signature(
        self,
        runtime_payload: dict[str, Any],
        envelope_payload: dict[str, Any],
    ) -> str:
        runtime_errors, normalized_runtime, _ = validate_runtime_constraints(
            runtime_payload,
            package_root=self.package_root,
            operator_root=self.operator_root,
        )
        runtime_comparable = normalized_runtime if not runtime_errors else dict(runtime_payload)
        runtime_comparable.pop("generated_at", None)

        envelope_errors, normalized_envelope, _ = validate_operator_runtime_envelope_spec(
            envelope_payload,
            runtime_constraints=normalized_runtime if not runtime_errors else dict(runtime_payload),
            trusted_source_bindings=self.binding_payload,
            backend_probe=dict(self._operator_status_snapshot.get("runtime_backend_probe", {})),
            enforce_backend_availability=False,
        )
        envelope_comparable = normalized_envelope if not envelope_errors else dict(envelope_payload)
        envelope_comparable.pop("generated_at", None)
        return stable_runtime_constraints_signature(
            {
                "runtime_constraints": runtime_comparable,
                "runtime_envelope": envelope_comparable,
            }
        )

    def _constraints_payload_from_form(self) -> dict[str, Any]:
        payload = build_default_runtime_constraints(self.package_root)
        payload["constraints"].update(
            {
                "max_memory_mb": int(self.constraint_vars["max_memory_mb"].get()),
                "max_python_threads": int(self.constraint_vars["max_python_threads"].get()),
                "max_child_processes": int(self.constraint_vars["max_child_processes"].get()),
                "subprocess_mode": str(self.constraint_vars["subprocess_mode"].get()),
                "working_directory": str(self.constraint_vars["working_directory"].get().strip()),
                "allowed_write_roots": [
                    part.strip()
                    for part in str(self.constraint_vars["allowed_write_roots"].get()).split(";")
                    if part.strip()
                ],
                "session_time_limit_seconds": int(self.constraint_vars["session_time_limit_seconds"].get()),
            }
        )
        return payload

    def _envelope_payload_from_form(self) -> dict[str, Any]:
        payload = build_default_operator_runtime_envelope_spec(self.package_root)
        intents = dict(payload.get("constraint_intents", {}))
        cpu_limit_text = str(self.envelope_vars["cpu_limit_cpus"].get()).strip()
        intents["cpu_limit_cpus"] = None if not cpu_limit_text else float(cpu_limit_text)
        intents["network_policy_intent"] = str(self.envelope_vars["network_policy_intent"].get()).strip() or "deny_all"
        payload["constraint_intents"] = intents
        payload["backend_kind"] = str(self.envelope_vars["backend_kind"].get()).strip() or BACKEND_LOCAL_GUARDED
        docker_settings = dict(payload.get("backend_settings", {}).get(BACKEND_LOCAL_DOCKER, {}))
        docker_settings["image"] = str(self.envelope_vars["docker_image"].get().strip() or "python:3.12-slim")
        payload["backend_settings"][BACKEND_LOCAL_DOCKER] = docker_settings
        return payload

    def _validate_constraints_payload_from_form(
        self,
    ) -> tuple[bool, dict[str, Any], list[str], dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
        try:
            payload = self._constraints_payload_from_form()
            envelope_payload = self._envelope_payload_from_form()
        except Exception as exc:
            self.constraints_status_var.set(f"Constraint parsing failed: {exc}")
            self.runtime_backend_status_var.set(f"Runtime envelope parsing failed: {exc}")
            return False, {}, [f"constraint parsing failed: {exc}"], {}, {}, [f"runtime envelope parsing failed: {exc}"], {}
        errors, normalized, enforcement = validate_runtime_constraints(
            payload,
            package_root=self.package_root,
            operator_root=self.operator_root,
        )
        envelope_errors, normalized_envelope, effective_envelope = validate_operator_runtime_envelope_spec(
            envelope_payload,
            runtime_constraints=normalized,
            trusted_source_bindings=self.binding_payload,
            backend_probe=dict(self._operator_status_snapshot.get("runtime_backend_probe", {})),
            enforce_backend_availability=True,
        )
        return (
            len(errors) == 0 and len(envelope_errors) == 0,
            normalized,
            errors,
            enforcement,
            normalized_envelope,
            envelope_errors,
            effective_envelope,
        )

    def _refresh_constraints_summary_from_snapshot(self) -> None:
        self._refresh_operator_status_snapshot()
        self.constraints_summary_text.delete("1.0", tk.END)
        self.constraints_summary_text.insert("1.0", render_constraints_summary(self._operator_status_snapshot))
        runtime_valid = bool(self._operator_status_snapshot.get("runtime_constraints_valid", False))
        errors = list(self._operator_status_snapshot.get("runtime_constraints_errors", []))
        runtime_constraints_path = str(self._operator_status_snapshot.get("runtime_constraints_path", "")).strip()
        runtime_envelope_valid = bool(self._operator_status_snapshot.get("runtime_envelope_spec_valid", False))
        runtime_envelope_errors = list(self._operator_status_snapshot.get("runtime_envelope_spec_errors", []))
        runtime_envelope_path = str(self._operator_status_snapshot.get("runtime_envelope_spec_path", "")).strip()
        backend_probe = dict(self._operator_status_snapshot.get("runtime_backend_probe", {}))
        available_backends = list(backend_probe.get("available_backends", []))
        selected_backend = str(
            dict(self._operator_status_snapshot.get("runtime_envelope_spec", {})).get("backend_kind", BACKEND_LOCAL_GUARDED)
        )
        backend_status = dict(dict(backend_probe.get("backends", {})).get(selected_backend, {}))
        combo_values = list(dict.fromkeys([BACKEND_LOCAL_GUARDED, *available_backends, selected_backend]))
        self.envelope_backend_combo.configure(values=tuple(combo_values))
        self.constraints_status_var.set(
            (
                "Runtime policy valid and saved."
                + (f" Applied source: {runtime_constraints_path}" if runtime_constraints_path else "")
            )
            if runtime_valid and runtime_envelope_valid
            else (
                f"Runtime policy invalid: {errors + runtime_envelope_errors}"
                + (f" Source: {runtime_constraints_path}" if runtime_constraints_path else "")
            )
        )
        self.runtime_backend_status_var.set(
            (
                f"Selected backend: {selected_backend} / "
                f"{backend_status.get('availability_class', 'unknown')} / "
                f"{backend_status.get('reason', 'status unavailable')}"
                + (f" Envelope source: {runtime_envelope_path}" if runtime_envelope_path else "")
            )
        )

    def _validate_constraints(self) -> bool:
        (
            valid,
            normalized,
            errors,
            enforcement,
            normalized_envelope,
            envelope_errors,
            effective_envelope,
        ) = self._validate_constraints_payload_from_form()
        preview_snapshot = {
            "runtime_constraints": {
                "valid": valid,
                "errors": errors,
                "constraints": normalized,
                "enforcement": enforcement,
            },
            "runtime_envelope": {
                "valid": len(envelope_errors) == 0,
                "errors": envelope_errors,
                "spec": normalized_envelope,
                "effective": effective_envelope,
            },
        }
        self.constraints_summary_text.delete("1.0", tk.END)
        self.constraints_summary_text.insert("1.0", render_constraints_summary(preview_snapshot))
        self.constraints_status_var.set(
            "Runtime policy valid."
            if valid
            else f"Runtime policy invalid: {errors + envelope_errors}"
        )
        selected_backend = str(normalized_envelope.get("backend_kind", BACKEND_LOCAL_GUARDED))
        self.runtime_backend_status_var.set(
            "Runtime envelope valid."
            if not envelope_errors
            else f"Runtime envelope invalid for {selected_backend}: {envelope_errors}"
        )
        self._update_launch_readiness()
        return valid

    def _save_constraints(self) -> None:
        (
            valid,
            normalized,
            errors,
            enforcement,
            normalized_envelope,
            envelope_errors,
            effective_envelope,
        ) = self._validate_constraints_payload_from_form()
        preview_snapshot = {
            "runtime_constraints": {
                "valid": valid,
                "errors": errors,
                "constraints": normalized,
                "enforcement": enforcement,
            },
            "runtime_envelope": {
                "valid": len(envelope_errors) == 0,
                "errors": envelope_errors,
                "spec": normalized_envelope,
                "effective": effective_envelope,
            },
        }
        self.constraints_summary_text.delete("1.0", tk.END)
        self.constraints_summary_text.insert("1.0", render_constraints_summary(preview_snapshot))
        if not valid:
            self.constraints_status_var.set(f"Runtime policy invalid: {errors + envelope_errors}")
            self.runtime_backend_status_var.set(
                f"Runtime envelope invalid: {envelope_errors}" if envelope_errors else self.runtime_backend_status_var.get()
            )
            messagebox.showerror("Runtime Constraints", "Fix runtime policy validation errors before saving.")
            self._update_launch_readiness()
            return
        save_runtime_constraints(normalized, root=self.operator_root)
        save_runtime_envelope_spec(normalized_envelope, root=self.operator_root)
        self.runtime_constraints_payload = load_runtime_constraints_or_default(
            root=self.operator_root,
            package_root=self.package_root,
        )
        self.runtime_envelope_payload = load_runtime_envelope_spec_or_default(
            root=self.operator_root,
            package_root=self.package_root,
        )
        self._saved_runtime_policy_signature = self._runtime_policy_signature(
            self.runtime_constraints_payload,
            self.runtime_envelope_payload,
        )
        runtime_constraints_path = str(operator_runtime_constraints_path(self.operator_root))
        runtime_envelope_path = str(operator_runtime_envelope_spec_path(self.operator_root))
        self._refresh_constraints_summary_from_snapshot()
        self._refresh_status_dashboard()
        self._update_launch_readiness()
        messagebox.showinfo(
            "Runtime Constraints",
            (
                "Runtime policy saved and applied for future launches."
                f"\n\nRuntime constraints source: {runtime_constraints_path}"
                f"\nRuntime envelope source: {runtime_envelope_path}"
            ),
        )

    def _constraints_dirty(self) -> bool:
        try:
            errors, normalized, _ = validate_runtime_constraints(
                self._constraints_payload_from_form(),
                package_root=self.package_root,
                operator_root=self.operator_root,
            )
            envelope_payload = self._envelope_payload_from_form()
            envelope_errors, normalized_envelope, _ = validate_operator_runtime_envelope_spec(
                envelope_payload,
                runtime_constraints=normalized if not errors else self._constraints_payload_from_form(),
                trusted_source_bindings=self.binding_payload,
                backend_probe=dict(self._operator_status_snapshot.get("runtime_backend_probe", {})),
                enforce_backend_availability=False,
            )
            if errors or envelope_errors:
                return True
            current = self._runtime_policy_signature(normalized, normalized_envelope)
        except Exception:
            return True
        return current != self._saved_runtime_policy_signature

    def _update_launch_readiness(self) -> None:
        self._refresh_operator_status_snapshot()
        self._update_directive_validation()
        readiness = build_launch_readiness(
            resume_mode=self.resume_mode_var.get().strip(),
            launch_action=self.launch_action_var.get().strip(),
            state_root=self.state_root_var.get().strip(),
            directive_summary=self._directive_summary,
            operator_status_snapshot=self._operator_status_snapshot,
            constraints_dirty=self._constraints_dirty(),
        )
        self.launch_readiness_var.set(render_launch_readiness(readiness=readiness))
        self.launch_button.configure(
            text="Initialize" if self.resume_mode_var.get().strip() == "new_bootstrap" else "Resume"
        )
        if readiness["can_launch"]:
            self.launch_button.state(["!disabled"])
        else:
            self.launch_button.state(["disabled"])

    def _launch_selected_action(self) -> None:
        readiness = build_launch_readiness(
            resume_mode=self.resume_mode_var.get().strip(),
            launch_action=self.launch_action_var.get().strip(),
            state_root=self.state_root_var.get().strip(),
            directive_summary=self._directive_summary,
            operator_status_snapshot=self._operator_status_snapshot,
            constraints_dirty=self._constraints_dirty(),
        )
        if not readiness["can_launch"]:
            messagebox.showerror("Launch Refused", render_launch_readiness(readiness=readiness))
            self.launch_status_var.set("Launch blocked before operator-mode startup.")
            self.launch_output_text.delete("1.0", tk.END)
            self.launch_output_text.insert("1.0", render_launch_readiness(readiness=readiness))
            return
        self.launch_status_var.set("Launching canonical operator flow...")
        self.launch_output_text.delete("1.0", tk.END)
        worker = threading.Thread(target=self._launch_worker, daemon=True)
        worker.start()

    def _launch_worker(self) -> None:
        directive_file = self.directive_file_var.get().strip() if self.resume_mode_var.get() == "new_bootstrap" else None
        try:
            result = launch_novali_main(
                package_root=self.package_root,
                operator_root=self.operator_root,
                directive_file=directive_file,
                state_root=self.state_root_var.get().strip(),
                launch_action=self.launch_action_var.get().strip(),
                wait=True,
            )
            self.after(0, lambda: self._handle_launch_result(result))
        except OperatorLaunchRefusedError as exc:
            self.after(0, lambda: self._handle_launch_refusal(exc))
        except Exception as exc:
            self.after(0, lambda: self._handle_launch_failure(exc))

    def _handle_launch_result(self, result: dict[str, Any]) -> None:
        summary = build_launch_result_summary(result)
        self.launch_status_var.set(summary["headline"])
        self.launch_output_text.delete("1.0", tk.END)
        self.launch_output_text.insert(
            "1.0",
            summary["summary"] + "\n\nRaw result:\n" + _pretty(result),
        )
        self._refresh_status_dashboard()
        self._update_launch_readiness()

    def _handle_launch_refusal(self, exc: OperatorLaunchRefusedError) -> None:
        summary = build_launch_refusal_summary(str(exc), list(exc.errors))
        self.launch_status_var.set(summary["headline"])
        self.launch_output_text.delete("1.0", tk.END)
        self.launch_output_text.insert(
            "1.0",
            summary["summary"] + "\n\nRaw refusal:\n" + _pretty({"message": str(exc), "errors": exc.errors}),
        )
        self._refresh_status_dashboard()
        self._update_launch_readiness()

    def _handle_launch_failure(self, exc: Exception) -> None:
        self.launch_status_var.set("Launch failed unexpectedly.")
        self.launch_output_text.delete("1.0", tk.END)
        self.launch_output_text.insert("1.0", f"{type(exc).__name__}: {exc}")
        self._refresh_status_dashboard()
        self._update_launch_readiness()

    def _refresh_status_dashboard(self) -> None:
        snapshot = build_operator_dashboard_snapshot(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root_var.get().strip() or (self.package_root / "data"),
        )
        rendered = render_dashboard_summary(snapshot)
        if bool(self.show_raw_status_var.get()):
            rendered = rendered + "\n\nRaw snapshot:\n" + _pretty(snapshot)
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert("1.0", rendered)

    def _export_acceptance_snapshot(self) -> None:
        default_dir = self.operator_root / "acceptance_reports"
        default_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = default_dir / f"novali_v5_manual_acceptance_{timestamp}.md"
        chosen_path = filedialog.asksaveasfilename(
            initialdir=str(default_dir),
            initialfile=default_path.name,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
        )
        if not chosen_path:
            return
        evidence = build_manual_acceptance_evidence(
            package_root=self.package_root,
            operator_root=self.operator_root,
            state_root=self.state_root_var.get().strip() or (self.package_root / "data"),
            directive_file=self.directive_file_var.get().strip() or None,
        )
        output_path = write_manual_acceptance_report(
            output_path=chosen_path,
            evidence=evidence,
        )
        self.launch_status_var.set(f"Manual acceptance snapshot exported: {output_path}")
        messagebox.showinfo(
            "Acceptance Snapshot",
            f"Manual acceptance snapshot written to:\n{output_path}",
        )


def launch_operator_gui(*, package_root: str | Path | None = None, operator_root: str | Path | None = None) -> None:
    app = OperatorShellApp(package_root=package_root, operator_root=operator_root)
    app.mainloop()
