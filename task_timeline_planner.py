# pyinstaller --onefile --windowed --name "TaskTimeline" task_timeline_planner.py
"""
Task Timeline Planner — A light-themed desktop app for managing tasks on a visual timeline.
"""

import json
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date, timedelta
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import calendar

# ── Colours ──────────────────────────────────────────────────────────────────
BG       = "#f5f5f9"
SURFACE  = "#ffffff"
SURFACE2 = "#eaebf0"
ACCENT   = "#6c5ce7"
TEXT     = "#2d3436"
MUTED    = "#9ba4b0"
BORDER   = "#dfe1e8"

# Rotating palette for tasks (no categories — colour by task order)
PALETTE = ["#6c5ce7", "#e06c9a", "#00b894", "#f39c12", "#0984e3", "#6c757d",
           "#e74c3c", "#2ecc71", "#f1c40f", "#a55eea"]

DATE_FMT = "%Y-%m-%d"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class DatePicker(ttk.Frame):
    """Compact date picker with Year, Month, Day dropdowns."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        today = date.today()
        font = ("Segoe UI", 9)

        self.var_year = tk.StringVar(value=str(today.year))
        self.var_month = tk.StringVar(value=MONTHS[today.month - 1])
        self.var_day = tk.StringVar(value=str(today.day))

        years = [str(y) for y in range(today.year - 2, today.year + 6)]

        self.cmb_year = ttk.Combobox(self, textvariable=self.var_year,
                                      values=years, width=5, state="readonly", font=font)
        self.cmb_month = ttk.Combobox(self, textvariable=self.var_month,
                                       values=MONTHS, width=4, state="readonly", font=font)
        self.cmb_day = ttk.Combobox(self, textvariable=self.var_day,
                                     values=self._day_list(), width=3, state="readonly", font=font)

        self.cmb_year.pack(side=tk.LEFT, padx=(0, 3))
        self.cmb_month.pack(side=tk.LEFT, padx=(0, 3))
        self.cmb_day.pack(side=tk.LEFT)

        # Update day list when month/year changes
        self.var_year.trace_add("write", lambda *_: self._update_days())
        self.var_month.trace_add("write", lambda *_: self._update_days())

    def _day_list(self):
        try:
            y = int(self.var_year.get())
            m = MONTHS.index(self.var_month.get()) + 1
            n = calendar.monthrange(y, m)[1]
        except (ValueError, IndexError):
            n = 31
        return [str(d) for d in range(1, n + 1)]

    def _update_days(self):
        days = self._day_list()
        self.cmb_day.configure(values=days)
        if self.var_day.get() not in days:
            self.var_day.set(days[-1])

    def get_date(self):
        y = int(self.var_year.get())
        m = MONTHS.index(self.var_month.get()) + 1
        d = int(self.var_day.get())
        return date(y, m, d)

    def get_date_str(self):
        return self.get_date().strftime(DATE_FMT)

    def set_date(self, d):
        if isinstance(d, str):
            d = datetime.strptime(d, DATE_FMT).date()
        self.var_year.set(str(d.year))
        self.var_month.set(MONTHS[d.month - 1])
        self.var_day.set(str(d.day))


def new_task(name, start, end):
    return {"id": str(uuid.uuid4()), "name": name,
            "start_date": start, "end_date": end}


def is_milestone(task):
    return task["start_date"] == task["end_date"]


class TaskTimelinePlanner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Task Timeline Planner")
        self.geometry("1200x780")
        self.configure(bg=BG)
        self.minsize(900, 600)

        self.tasks: list[dict] = []
        self.filepath: str | None = None
        self.unsaved = False
        self._drag_info = None
        self._bar_rects = []

        self._build_styles()
        self._build_menu()
        self._build_ui()
        self._refresh_chart()

        self.protocol("WM_DELETE_WINDOW", self._on_exit)
        self.bind("<Control-n>", lambda e: self._file_new())
        self.bind("<Control-o>", lambda e: self._file_open())
        self.bind("<Control-s>", lambda e: self._file_save())

    # ── Styles ───────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE,
                     borderwidth=0, font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 8))
        s.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground=ACCENT, background=BG)
        s.configure("Sub.TLabel", font=("Segoe UI", 9), foreground=MUTED, background=BG)

        s.configure("Accent.TButton", background=ACCENT, foreground="#fff",
                     font=("Segoe UI", 10, "bold"), padding=(12, 8))
        s.map("Accent.TButton", background=[("active", "#6a5fd6"), ("pressed", "#5a4fc6")])

        s.configure("Flat.TButton", background=SURFACE2, foreground=TEXT,
                     font=("Segoe UI", 9), padding=(8, 5))
        s.map("Flat.TButton", background=[("active", SURFACE)])

        s.configure("TCheckbutton", background=BG, foreground=TEXT)
        s.map("TCheckbutton", background=[("active", BG)])

        s.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                     insertcolor=TEXT, padding=6)
        s.configure("TCombobox", fieldbackground=SURFACE, foreground=TEXT)

        s.configure("Treeview", background=SURFACE, foreground=TEXT,
                     fieldbackground=SURFACE, rowheight=30, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=SURFACE2, foreground=TEXT,
                     font=("Segoe UI", 9, "bold"), padding=4)
        s.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "#fff")])

        s.configure("TSeparator", background=BORDER)

    # ── Menu ─────────────────────────────────────────────────────────────
    def _build_menu(self):
        mbar = tk.Menu(self, bg=SURFACE, fg=TEXT, activebackground=ACCENT,
                       activeforeground="#fff", tearoff=0)
        fm = tk.Menu(mbar, bg=SURFACE, fg=TEXT, activebackground=ACCENT,
                     activeforeground="#fff", tearoff=0)
        fm.add_command(label="New          Ctrl+N", command=self._file_new)
        fm.add_command(label="Open…        Ctrl+O", command=self._file_open)
        fm.add_separator()
        fm.add_command(label="Save         Ctrl+S", command=self._file_save)
        fm.add_command(label="Save As…", command=self._file_save_as)
        fm.add_separator()
        fm.add_command(label="Export PNG…", command=lambda: self._export("png"))
        fm.add_command(label="Export PDF…", command=lambda: self._export("pdf"))
        fm.add_separator()
        fm.add_command(label="Exit", command=self._on_exit)
        mbar.add_cascade(label="File", menu=fm)
        self.config(menu=mbar)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Left panel ──
        left = ttk.Frame(self, width=380)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(14, 0), pady=14)
        left.pack_propagate(False)

        # -- Form --
        ttk.Label(left, text="New Task", style="Header.TLabel").pack(anchor="w")
        ttk.Label(left, text="Fill in the details and click Add", style="Sub.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Label(left, text="Task Name").pack(anchor="w", pady=(0, 3))
        self.entry_name = ttk.Entry(left, font=("Segoe UI", 10))
        self.entry_name.pack(fill=tk.X, ipady=2)
        self.entry_name.bind("<Button-1>", lambda e: self.entry_name.focus_set())
        self.entry_name.bind("<Return>", lambda e: self._add_task())

        self.var_milestone = tk.BooleanVar()
        ttk.Checkbutton(left, text="Milestone (single date)",
                         variable=self.var_milestone, command=self._toggle_end
                         ).pack(anchor="w", pady=(10, 6))

        dates_frame = ttk.Frame(left)
        dates_frame.pack(fill=tk.X)

        lf_start = ttk.Frame(dates_frame)
        lf_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(lf_start, text="Start Date").pack(anchor="w", pady=(0, 3))
        self.date_start = DatePicker(lf_start)
        self.date_start.pack(fill=tk.X)

        self.lf_end = ttk.Frame(dates_frame)
        self.lf_end.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Label(self.lf_end, text="End Date").pack(anchor="w", pady=(0, 3))
        self.date_end = DatePicker(self.lf_end)
        self.date_end.pack(fill=tk.X)

        ttk.Button(left, text="Add Task", style="Accent.TButton",
                    command=self._add_task).pack(fill=tk.X, pady=(14, 0), ipady=2)

        # -- Separator --
        sep = ttk.Frame(left, height=1, style="TFrame")
        sep.pack(fill=tk.X, pady=16)
        tk.Frame(sep, bg=BORDER, height=1).pack(fill=tk.X)

        # -- Task list header row --
        hdr = ttk.Frame(left)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="Tasks", style="Header.TLabel").pack(side=tk.LEFT)
        self.lbl_count = ttk.Label(hdr, text="0 items", style="Sub.TLabel")
        self.lbl_count.pack(side=tk.RIGHT, pady=(4, 0))

        # -- Treeview --
        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        cols = ("name", "start", "end", "type")
        self.tree = ttk.Treeview(tree_wrap, columns=cols, show="headings",
                                  selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.heading("start", text="Start")
        self.tree.heading("end", text="End")
        self.tree.heading("type", text="Type")
        self.tree.column("name", width=140, minwidth=80)
        self.tree.column("start", width=85, minwidth=70)
        self.tree.column("end", width=85, minwidth=70)
        self.tree.column("type", width=70, minwidth=55)

        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_chart())

        # Context menu
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=SURFACE, fg=TEXT,
                                 activebackground=ACCENT, activeforeground="#fff")
        self.ctx_menu.add_command(label="Edit", command=self._edit_task)
        self.ctx_menu.add_command(label="Delete", command=self._delete_task)
        self.tree.bind("<Button-3>", self._show_ctx)

        # -- Action buttons --
        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Edit", style="Flat.TButton",
                    command=self._edit_task).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))
        ttk.Button(btn_row, text="Delete", style="Flat.TButton",
                    command=self._delete_task).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(3, 0))

        # ── Right panel — Chart ──
        chart_frame = ttk.Frame(self)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 14), pady=14)

        self.fig, self.ax = plt.subplots(figsize=(7, 5))
        self.fig.patch.set_alpha(0.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().configure(takefocus=False)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("button_press_event", self._on_chart_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_chart_motion)
        self.canvas.mpl_connect("button_release_event", self._on_chart_release)

    # ── Helpers ──────────────────────────────────────────────────────────
    def _toggle_end(self):
        if self.var_milestone.get():
            self.lf_end.pack_forget()
        else:
            self.lf_end.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def _get_date_str(self, widget):
        return widget.get_date_str()

    def _task_color(self, task):
        """Consistent colour per task based on its position."""
        try:
            idx = next(i for i, t in enumerate(self.tasks) if t["id"] == task["id"])
        except StopIteration:
            idx = 0
        return PALETTE[idx % len(PALETTE)]

    # ── CRUD ─────────────────────────────────────────────────────────────
    def _add_task(self):
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("Input", "Task name is required.")
            return
        start = self._get_date_str(self.date_start)
        end = start if self.var_milestone.get() else self._get_date_str(self.date_end)
        try:
            sd = datetime.strptime(start, DATE_FMT)
            ed = datetime.strptime(end, DATE_FMT)
            if ed < sd:
                messagebox.showwarning("Input", "End date cannot be before start date.")
                return
        except ValueError:
            messagebox.showwarning("Input", "Dates must be YYYY-MM-DD.")
            return
        self.tasks.append(new_task(name, start, end))
        self.unsaved = True
        self._sync_tree()
        self._refresh_chart()
        self.entry_name.delete(0, tk.END)
        self.entry_name.focus_set()

    def _delete_task(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.tasks = [t for t in self.tasks if t["id"] != sel[0]]
        self.unsaved = True
        self._sync_tree()
        self._refresh_chart()

    def _edit_task(self):
        sel = self.tree.selection()
        if not sel:
            return
        task = next((t for t in self.tasks if t["id"] == sel[0]), None)
        if task:
            self._open_edit_dialog(task)

    def _open_edit_dialog(self, task):
        dlg = tk.Toplevel(self)
        dlg.title("Edit Task")
        dlg.configure(bg=BG)
        dlg.geometry("360x260")
        dlg.transient(self)
        dlg.grab_set()

        pad = {"padx": 14}

        ttk.Label(dlg, text="Task Name").pack(anchor="w", pady=(14, 3), **pad)
        e_name = ttk.Entry(dlg, font=("Segoe UI", 10))
        e_name.insert(0, task["name"])
        e_name.pack(fill=tk.X, ipady=2, **pad)

        row = ttk.Frame(dlg)
        row.pack(fill=tk.X, pady=(10, 0), **pad)
        lf = ttk.Frame(row)
        lf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(lf, text="Start Date").pack(anchor="w", pady=(0, 3))
        e_start = ttk.Entry(lf, font=("Segoe UI", 10))
        e_start.insert(0, task["start_date"])
        e_start.pack(fill=tk.X, ipady=2)

        rf = ttk.Frame(row)
        rf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Label(rf, text="End Date").pack(anchor="w", pady=(0, 3))
        e_end = ttk.Entry(rf, font=("Segoe UI", 10))
        e_end.insert(0, task["end_date"])
        e_end.pack(fill=tk.X, ipady=2)

        def save():
            n = e_name.get().strip()
            if not n:
                messagebox.showwarning("Input", "Name required.", parent=dlg)
                return
            s, en = e_start.get().strip(), e_end.get().strip()
            try:
                sd = datetime.strptime(s, DATE_FMT)
                ed = datetime.strptime(en, DATE_FMT)
                if ed < sd:
                    messagebox.showwarning("Input", "End before start.", parent=dlg)
                    return
            except ValueError:
                messagebox.showwarning("Input", "Dates must be YYYY-MM-DD.", parent=dlg)
                return
            task["name"] = n
            task["start_date"] = s
            task["end_date"] = en
            self.unsaved = True
            self._sync_tree()
            self._refresh_chart()
            dlg.destroy()

        ttk.Button(dlg, text="Save Changes", style="Accent.TButton",
                    command=save).pack(fill=tk.X, pady=(18, 14), padx=14, ipady=2)

    def _show_ctx(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.ctx_menu.tk_popup(event.x_root, event.y_root)

    def _sync_tree(self):
        self.tree.delete(*self.tree.get_children())
        for t in self.tasks:
            if is_milestone(t):
                ttype = "1 day"
            else:
                days = (datetime.strptime(t["end_date"], DATE_FMT) - datetime.strptime(t["start_date"], DATE_FMT)).days
                ttype = f"{days} day{'s' if days != 1 else ''}"
            self.tree.insert("", tk.END, iid=t["id"],
                             values=(t["name"], t["start_date"], t["end_date"], ttype))
        n = len(self.tasks)
        self.lbl_count.configure(text=f"{n} item{'s' if n != 1 else ''}")

    # ── Chart ────────────────────────────────────────────────────────────
    def _refresh_chart(self):
        ax = self.ax
        ax.clear()
        ax.set_facecolor("none")

        if not self.tasks:
            ax.text(0.5, 0.5, "No tasks yet — add one to get started!",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=13, color=MUTED, style="italic")
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            self.fig.tight_layout()
            self.canvas.draw_idle()
            return

        sorted_tasks = sorted(self.tasks, key=lambda t: t["start_date"])

        all_dates = []
        for t in sorted_tasks:
            all_dates.append(datetime.strptime(t["start_date"], DATE_FMT))
            all_dates.append(datetime.strptime(t["end_date"], DATE_FMT))
        d_min, d_max = min(all_dates), max(all_dates)
        pad = max(timedelta(days=3), (d_max - d_min) * 0.08)
        d_min -= pad
        d_max += pad

        lanes = self._assign_lanes(sorted_tasks)
        n_lanes = max(lanes) + 1 if lanes else 1

        sel = self.tree.selection()
        sel_id = sel[0] if sel else None

        self._bar_rects = []
        line_y = 0.0
        lane_sp = 0.65

        # Axis line
        ax.axhline(y=line_y, color=MUTED, linewidth=1.5, zorder=1, alpha=0.5)

        # Today
        today = datetime.combine(date.today(), datetime.min.time())
        if d_min <= today <= d_max:
            tx = mdates.date2num(today)
            ax.axvline(x=tx, color=ACCENT, linewidth=1, linestyle="--", alpha=0.5, zorder=2)
            ax.text(tx, line_y + n_lanes * lane_sp * 0.5 + 0.35, "Today",
                    ha="center", va="bottom", fontsize=8, color=ACCENT, alpha=0.7)

        for i, task in enumerate(sorted_tasks):
            sd = datetime.strptime(task["start_date"], DATE_FMT)
            ed = datetime.strptime(task["end_date"], DATE_FMT)
            color = self._task_color(task)
            lane = lanes[i]

            if lane % 2 == 0:
                y_off = line_y + (lane // 2 + 1) * lane_sp
                va, sign = "bottom", 1
            else:
                y_off = line_y - (lane // 2 + 1) * lane_sp
                va, sign = "top", -1

            label_y = y_off + sign * 0.14
            alpha = 1.0 if sel_id is None or task["id"] == sel_id else 0.3
            x_s = mdates.date2num(sd)
            x_e = mdates.date2num(ed)

            if is_milestone(task):
                ax.plot(x_s, line_y, "o", color=color, markersize=13, zorder=5, alpha=alpha)
                ax.plot(x_s, line_y, "o", color="#ffffff", markersize=5, zorder=6, alpha=alpha)
                ax.plot([x_s, x_s], [line_y, y_off], color=color, lw=1,
                        alpha=alpha * 0.5, zorder=3)
                ax.text(x_s, label_y, task["name"], ha="center", va=va,
                        fontsize=9, fontweight="bold",
                        color=TEXT if alpha > 0.5 else MUTED, zorder=7)
                ax.text(x_s, label_y + sign * 0.2, sd.strftime("%b %d"),
                        ha="center", va=va, fontsize=7, color=MUTED,
                        zorder=7, alpha=alpha)
                self._bar_rects.append((task, x_s, x_e, line_y, True))
            else:
                bar_h = 0.24
                ax.barh(y_off, x_e - x_s, left=x_s, height=bar_h,
                        color=color, alpha=alpha * 0.85, edgecolor="none",
                        zorder=4, linewidth=0)
                # Round caps
                for xp in (x_s, x_e):
                    ax.plot(xp, y_off, "o", color=color, markersize=7,
                            zorder=5, alpha=alpha)
                # Connectors
                for xp in (x_s, x_e):
                    ax.plot([xp, xp], [line_y, y_off], color=color, lw=0.8,
                            alpha=alpha * 0.3, zorder=3, linestyle=":")
                mid = (x_s + x_e) / 2
                ax.text(mid, label_y, task["name"], ha="center", va=va,
                        fontsize=9, fontweight="bold",
                        color=TEXT if alpha > 0.5 else MUTED, zorder=7)
                ax.text(mid, label_y + sign * 0.2,
                        f"{sd.strftime('%b %d')} – {ed.strftime('%b %d')}",
                        ha="center", va=va, fontsize=7, color=MUTED,
                        zorder=7, alpha=alpha)
                self._bar_rects.append((task, x_s, x_e, y_off, False))

        ax.set_xlim(mdates.date2num(d_min), mdates.date2num(d_max))
        y_ext = (n_lanes // 2 + 1) * lane_sp + 0.9
        ax.set_ylim(line_y - y_ext, line_y + y_ext)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.tick_params(axis="x", colors=MUTED, labelsize=8, length=0, pad=8)
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)

        # Overall duration summary
        earliest = min(all_dates)
        latest = max(all_dates)
        total_days = (latest - earliest).days
        if total_days == 0:
            dur_text = "1 day"
        else:
            weeks = total_days / 7
            if weeks >= 1:
                dur_text = f"{total_days} days / {weeks:.1f} weeks"
            else:
                dur_text = f"{total_days} day{'s' if total_days != 1 else ''}"
        dur_label = f"Overall duration: {earliest.strftime('%b %d, %Y')} → {latest.strftime('%b %d, %Y')}  ·  {dur_text}"
        ax.text(0.5, -0.06, dur_label, transform=ax.transAxes,
                ha="center", va="top", fontsize=8.5, color=MUTED)

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw_idle()

    def _assign_lanes(self, sorted_tasks):
        lanes, ends = [], []
        for t in sorted_tasks:
            sd = datetime.strptime(t["start_date"], DATE_FMT).toordinal()
            ed = datetime.strptime(t["end_date"], DATE_FMT).toordinal()
            placed = False
            for li, le in enumerate(ends):
                if sd > le + 1:
                    ends[li] = ed
                    lanes.append(li)
                    placed = True
                    break
            if not placed:
                lanes.append(len(ends))
                ends.append(ed)
        return lanes

    # ── Drag-to-resize ───────────────────────────────────────────────────
    def _on_chart_press(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        for task, x_s, x_e, y, is_ms in self._bar_rects:
            if is_ms:
                continue
            if abs(event.xdata - x_s) < 1.5:
                self._drag_info = {"task": task, "edge": "start"}
                return
            if abs(event.xdata - x_e) < 1.5:
                self._drag_info = {"task": task, "edge": "end"}
                return

    def _on_chart_motion(self, event):
        pass  # visual feedback reserved for future

    def _on_chart_release(self, event):
        if self._drag_info is None or event.inaxes != self.ax or event.xdata is None:
            self._drag_info = None
            return
        info = self._drag_info
        self._drag_info = None
        new_date = mdates.num2date(event.xdata).strftime(DATE_FMT)
        task = info["task"]
        try:
            nd = datetime.strptime(new_date, DATE_FMT)
            if info["edge"] == "start":
                if nd > datetime.strptime(task["end_date"], DATE_FMT):
                    return
                task["start_date"] = new_date
            else:
                if nd < datetime.strptime(task["start_date"], DATE_FMT):
                    return
                task["end_date"] = new_date
        except ValueError:
            return
        self.unsaved = True
        self._sync_tree()
        self._refresh_chart()

    # ── File I/O ─────────────────────────────────────────────────────────
    def _check_save(self):
        if not self.unsaved:
            return True
        ans = messagebox.askyesnocancel("Unsaved Changes",
                                         "Save changes before proceeding?")
        if ans is None:
            return False
        if ans:
            self._file_save()
        return True

    def _file_new(self):
        if not self._check_save():
            return
        self.tasks.clear()
        self.filepath = None
        self.unsaved = False
        self._sync_tree()
        self._refresh_chart()
        self.title("Task Timeline Planner")

    def _file_open(self):
        if not self._check_save():
            return
        fp = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not fp:
            return
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = data if isinstance(data, list) else data.get("tasks", [])
            self.filepath = fp
            self.unsaved = False
            self._sync_tree()
            self._refresh_chart()
            self.title(f"Task Timeline Planner — {fp}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def _file_save(self):
        if self.filepath:
            self._write_json(self.filepath)
        else:
            self._file_save_as()

    def _file_save_as(self):
        fp = filedialog.asksaveasfilename(defaultextension=".json",
                                           filetypes=[("JSON files", "*.json")])
        if not fp:
            return
        self.filepath = fp
        self._write_json(fp)
        self.title(f"Task Timeline Planner — {fp}")

    def _write_json(self, fp):
        try:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2)
            self.unsaved = False
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def _export(self, fmt):
        ext = f".{fmt}"
        fp = filedialog.asksaveasfilename(
            defaultextension=ext, filetypes=[(f"{fmt.upper()} files", f"*{ext}")])
        if not fp:
            return
        try:
            self.fig.savefig(fp, dpi=150, facecolor="white",
                             bbox_inches="tight")
            messagebox.showinfo("Export", f"Saved to {fp}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def _on_exit(self):
        if self._check_save():
            self.destroy()


if __name__ == "__main__":
    app = TaskTimelinePlanner()
    app.mainloop()
