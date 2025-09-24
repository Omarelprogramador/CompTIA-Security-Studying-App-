# app/ui.py
import tkinter as tk
from tkinter import messagebox
import json
import os
import random
from dataclasses import dataclass

from app.config import QUESTION_TIME_SECONDS, APP_TITLE, WINDOW_SIZE

@dataclass
class Question:
    qtype: str
    prompt: str
    options: list | None = None   # lista de dicts con keys: key, text{es}, correct
    pairs: list | None = None     # para "match"

class TestApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.config(bg="#f5f6f8")

        # Estado
        print(f"[DEBUG] __file__ = {__file__}")
        self.test_files: list[str] = self.find_test_files()
        print(f"[DEBUG] test_files found: {self.test_files}")
        if not self.test_files:
            messagebox.showerror("Error", "No se encontraron archivos de test en 'data/tests'.")
            print("[DEBUG] No test files found. App will close.")
            self.destroy()
            return

        self.questions: list[dict] = []
        self.current_idx: int = 0
        self.score: int = 0
        self.answered_current: bool = False
        self.timer_seconds_left: int = QUESTION_TIME_SECONDS
        self.timer_job = None
        self.user_answers = {}  # id_pregunta -> set/list de respuestas
        self.match_state = {}   # para pareo

        # Pantallas
        self.topbar = None
        self.content = tk.Frame(self, bg="#f5f6f8")
        self.content.pack(fill="both", expand=True)

        self.show_select_screen()

    # -------------------------
    # Utilidades / Datos
    # -------------------------
    def find_test_files(self):
        # Busca tests relativos a la raíz del proyecto: .../data/tests
        # (funciona tanto si ejecutas main.py como si pruebas ui.py solo)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"[DEBUG] script_dir: {script_dir}")
        project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
        print(f"[DEBUG] project_root: {project_root}")
        data_dir = os.path.join(project_root, 'data', 'tests')
        print(f"[DEBUG] data_dir: {data_dir}")
        os.makedirs(data_dir, exist_ok=True)
        files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        print(f"[DEBUG] files in data_dir: {files}")
        files.sort()
        # Guarda la ruta para uso posterior
        self._tests_dir = data_dir
        return files

    def load_questions_from_file(self, filename):
        path = os.path.join(self._tests_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            messagebox.showerror("Error", f"No se pudo cargar '{filename}': {e}")
            return []

        # Normalizamos t/f como sc (true/false son 2 opciones)
        for q in data:
            if q.get("type") == "t/f":
                q["type"] = "sc"
        return data

    def reset_state(self):
        self.current_idx = 0
        self.score = 0
        self.answered_current = False
        self.user_answers.clear()
        self.match_state.clear()
        self.stop_timer()
        self.timer_seconds_left = QUESTION_TIME_SECONDS

    # -------------------------
    # UI commons
    # -------------------------
    def clear_content(self):
        for w in self.winfo_children():
            w.destroy()
        self.content = tk.Frame(self, bg="#f5f6f8")
        self.content.pack(fill="both", expand=True)

    def build_topbar(self, show_home=True):
        top = tk.Frame(self, bg="#1f2937")
        top.pack(fill="x")
        title = tk.Label(top, text=APP_TITLE, fg="white", bg="#1f2937",
                         font=("Inter", 14, "bold"), padx=12, pady=8)
        title.pack(side="left")
        if show_home:
            tk.Button(top, text="Inicio", command=self.show_select_screen,
                      bg="#111827", fg="white", activebackground="#374151",
                      font=("Inter", 10, "bold"), relief="flat", padx=12, pady=6).pack(side="right", padx=8, pady=6)
        self.topbar = top

    # -------------------------
    # Pantalla: Selección de test
    # -------------------------
    def show_select_screen(self):
        self.stop_timer()
        self.clear_content()
        self.build_topbar(show_home=False)

        card = tk.Frame(self.content, bg="white", bd=1, relief="groove")
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.7)

        tk.Label(card, text="Selecciona un Test", bg="white", font=("Inter", 16, "bold")).pack(pady=20)

        box_frame = tk.Frame(card, bg="white")
        box_frame.pack(pady=10)
        self.lb = tk.Listbox(box_frame, width=50, height=14, font=("Inter", 12))
        self.lb.pack(side="left", fill="y", padx=(0, 6))
        sb = tk.Scrollbar(box_frame, orient="vertical", command=self.lb.yview)
        sb.pack(side="right", fill="y")
        self.lb.config(yscrollcommand=sb.set)

        for f in self.test_files:
            self.lb.insert(tk.END, f)

        btns = tk.Frame(card, bg="white")
        btns.pack(pady=16)
        tk.Button(btns, text="Comenzar", bg="#2563eb", fg="white", font=("Inter", 12, "bold"),
                  command=self.start_selected_test).pack(side="left", padx=6)
        tk.Button(btns, text="Salir", bg="#6b7280", fg="white", font=("Inter", 12),
                  command=self.destroy).pack(side="left", padx=6)

    def start_selected_test(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showwarning("Atención", "Selecciona un test.")
            return
        fname = self.lb.get(sel[0])
        self.questions = self.load_questions_from_file(fname)
        if not self.questions:
            return
        random.shuffle(self.questions)
        self.reset_state()
        self.show_question_screen()

    # -------------------------
    # Pantalla: Pregunta
    # -------------------------
    def show_question_screen(self):
        self.stop_timer()
        self.clear_content()
        self.build_topbar()

        # Barra de estado
        status = tk.Frame(self.content, bg="#e5e7eb", pady=6, padx=10)
        status.pack(fill="x")
        self.lbl_progress = tk.Label(status, bg="#e5e7eb", font=("Inter", 10, "bold"))
        self.lbl_progress.pack(side="left")
        self.lbl_score = tk.Label(status, bg="#e5e7eb", font=("Inter", 10, "bold"))
        self.lbl_score.pack(side="left", padx=16)
        self.lbl_timer = tk.Label(status, bg="#e5e7eb", font=("Inter", 10, "bold"))
        self.lbl_timer.pack(side="right")

        # Contenedor principal
        main = tk.Frame(self.content, bg="white", bd=1, relief="groove")
        main.pack(padx=16, pady=16, fill="both", expand=True)

        # Pregunta
        self.lbl_question = tk.Label(main, text="", wraplength=800, justify="left",
                                     bg="white", font=("Inter", 13))
        self.lbl_question.pack(padx=16, pady=(16, 8), anchor="w")

        # Contenedores de opciones/match
        self.options_frame = tk.Frame(main, bg="white")
        self.match_frame = tk.Frame(main, bg="white")
        self.options_frame.pack(fill="both", expand=True)

        # Botonera
        btns = tk.Frame(main, bg="white")
        btns.pack(fill="x", pady=8, padx=12)

        self.btn_prev = tk.Button(btns, text="Anterior", command=self.prev_question,
                                  bg="#374151", fg="white", font=("Inter", 10, "bold"))
        self.btn_prev.pack(side="left", padx=4)

        self.btn_check = tk.Button(btns, text="Comprobar", command=self.check_answer,
                                   bg="#10b981", fg="white", font=("Inter", 10, "bold"))
        self.btn_check.pack(side="left", padx=4)

        self.btn_next = tk.Button(btns, text="Siguiente", command=self.next_question,
                                  bg="#2563eb", fg="white", font=("Inter", 10, "bold"))
        self.btn_next.pack(side="right", padx=4)

        self.btn_pause = tk.Button(btns, text="Pausar", command=self.toggle_pause,
                                   bg="#f59e0b", fg="white", font=("Inter", 10, "bold"))
        self.btn_pause.pack(side="right", padx=4)

        self.load_current_question()
        self.start_timer()

    def load_current_question(self):
        q = self.questions[self.current_idx]
        prompt_es = q["prompt"]["es"]
        qtype = q["type"]

        self.lbl_question.config(text=f"Pregunta {self.current_idx + 1}: {prompt_es}")
        for w in self.options_frame.winfo_children():
            w.destroy()
        for w in self.match_frame.winfo_children():
            w.destroy()

        self.answer_widgets = {}
        self.radio_var = None
        self.answered_current = False

        if qtype in ("sc", "t/f"):
            self.radio_var = tk.StringVar(value="")
            for opt in q["options"]:
                rb = tk.Radiobutton(self.options_frame,
                                    text=f"{opt['key']}. {opt['text']['es']}",
                                    variable=self.radio_var, value=opt["key"],
                                    bg="white", anchor="w", font=("Inter", 11))
                rb.pack(fill="x", padx=16, pady=4)
                self.answer_widgets[opt["key"]] = rb

        elif qtype == "ms":
            for opt in q["options"]:
                var = tk.IntVar(value=0)
                cb = tk.Checkbutton(self.options_frame,
                                    text=f"{opt['key']}. {opt['text']['es']}",
                                    variable=var, bg="white", anchor="w", font=("Inter", 11))
                cb.var = var # type: ignore
                cb.pack(fill="x", padx=16, pady=4)
                self.answer_widgets[opt["key"]] = cb

        elif qtype == "match":
            self.options_frame.pack_forget()
            self.match_frame.pack(fill="both", expand=True)
            self.build_match_ui(q)

        # Estado/botones
        self.update_statusbar()
        self.update_nav_buttons()
        self.timer_seconds_left = QUESTION_TIME_SECONDS

    # ---- MATCH UI ----
    def build_match_ui(self, q):
        pairs = q["pairs"]
        self.match_state = {}  # pregunta -> botón (respuesta) asignado

        left = tk.Frame(self.match_frame, bg="white", padx=12, pady=12)
        right = tk.Frame(self.match_frame, bg="white", padx=12, pady=12)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(left, text="Preguntas", bg="white", font=("Inter", 11, "bold")).pack(anchor="w")
        tk.Label(right, text="Respuestas", bg="white", font=("Inter", 11, "bold")).pack(anchor="w")

        self.q_labels = {}
        self.a_buttons = {}
        answers = [p["answer"]["es"] for p in pairs]
        random.shuffle(answers)

        for p in pairs:
            lbl = tk.Label(left, text=p["question"]["es"], bg="white",
                           anchor="w", justify="left", relief="solid", bd=1, padx=6, pady=6)
            lbl.pack(fill="x", pady=4)
            self.q_labels[p["question"]["es"]] = lbl

        for ans in answers:
            btn = tk.Button(right, text=ans, bg="#e5e7eb", relief="raised")
            btn.pack(fill="x", pady=4)
            btn.bind("<Button-1>", self.start_drag)
            btn.bind("<B1-Motion>", self.do_drag)
            btn.bind("<ButtonRelease-1>", self.stop_drag)
            self.a_buttons[ans] = btn

        # mapa correcto
        self.correct_pairs = {p["question"]["es"]: p["answer"]["es"] for p in pairs}

    # ---- Drag & Drop básico ----
    def start_drag(self, ev):
        self.drag_item = ev.widget
        self.drag_item.lift()
        self._drag_start = (ev.x, ev.y)

    def do_drag(self, ev):
        x = self.drag_item.winfo_x() - self._drag_start[0] + ev.x
        y = self.drag_item.winfo_y() - self._drag_start[1] + ev.y
        self.drag_item.place(in_=self.drag_item.master, x=x, y=y)

    def stop_drag(self, ev):
        # ¿soltó encima de una etiqueta?
        for q_text, q_lbl in self.q_labels.items():
            if self.widget_overlap(self.drag_item, q_lbl):
                # si ya había algo, lo devolvemos a su sitio
                for k, btn in list(self.match_state.items()):
                    if btn is self.drag_item:
                        del self.match_state[k]
                self.match_state[q_text] = self.drag_item
                # anclar visualmente
                self.drag_item.place_forget()
                self.drag_item.pack(in_=q_lbl, side="right", padx=6)
                break
        else:
            # si no cayó en ninguna, lo devolvemos a columna derecha
            self.drag_item.place_forget()
            self.drag_item.pack(in_=self.drag_item.master, fill="x", pady=4)

    def widget_overlap(self, a, b):
        ax1, ay1 = a.winfo_rootx(), a.winfo_rooty()
        ax2, ay2 = ax1 + a.winfo_width(), ay1 + a.winfo_height()
        bx1, by1 = b.winfo_rootx(), b.winfo_rooty()
        bx2, by2 = bx1 + b.winfo_width(), by1 + b.winfo_height()
        return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)

    # -------------------------
    # Timer
    # -------------------------
    def start_timer(self):
        self.stop_timer()
        self.update_timer_label()
        self.timer_job = self.after(1000, self._tick)

    def stop_timer(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None

    def _tick(self):
        if self.timer_seconds_left <= 0:
            # tiempo agotado -> auto comprobar y avanzar
            if not self.answered_current:
                self.check_answer(auto=True)
            self.next_question()
            return
        self.timer_seconds_left -= 1
        self.update_timer_label()
        self.timer_job = self.after(1000, self._tick)

    def toggle_pause(self):
        if self.timer_job:
            self.stop_timer()
            self.btn_pause.config(text="Reanudar")
        else:
            self.start_timer()
            self.btn_pause.config(text="Pausar")

    def update_timer_label(self):
        mm = self.timer_seconds_left // 60
        ss = self.timer_seconds_left % 60
        self.lbl_timer.config(text=f"⏱ {mm:02d}:{ss:02d}")

    # -------------------------
    # Navegación / Estado
    # -------------------------
    def update_statusbar(self):
        total = len(self.questions)
        self.lbl_progress.config(text=f"Pregunta {self.current_idx + 1}/{total}")
        self.lbl_score.config(text=f"Puntuación: {self.score}")

    def update_nav_buttons(self):
        self.btn_prev.config(state="normal" if self.current_idx > 0 else "disabled")
        self.btn_next.config(state="normal" if self.current_idx < len(self.questions) - 1 else "disabled")
        self.btn_check.config(state="normal")

    def save_user_answer(self, selected):
        qid = self.questions[self.current_idx].get("id", f"Q{self.current_idx}")
        self.user_answers[qid] = selected

    def check_answer(self, auto=False):
        if self.answered_current:
            return
        q = self.questions[self.current_idx]
        qtype = q["type"]
        correct = False

        if qtype == "sc":
            choice = ""
            if hasattr(self, "radio_var") and self.radio_var:
                choice = self.radio_var.get()
            if not choice and not auto:
                messagebox.showinfo("Info", "Selecciona una opción.")
                return
            correct_keys = {opt["key"] for opt in q["options"] if opt["correct"]}
            correct = choice in correct_keys
            # Colorear
            for key, rb in self.answer_widgets.items():
                if key in correct_keys:
                    rb.config(fg="green")
                elif key == choice and key not in correct_keys:
                    rb.config(fg="red")

            self.save_user_answer(choice)

        elif qtype == "ms":
            selected = {k for k, cb in self.answer_widgets.items() if cb.var.get() == 1}
            correct_keys = {opt["key"] for opt in q["options"] if opt["correct"]}
            if not selected and not auto:
                messagebox.showinfo("Info", "Selecciona al menos una opción.")
                return
            correct = selected == correct_keys  # exact match
            for k, cb in self.answer_widgets.items():
                if k in correct_keys and k in selected:
                    cb.config(fg="green")
                elif k in correct_keys and k not in selected:
                    cb.config(fg="orange")
                elif k not in correct_keys and k in selected:
                    cb.config(fg="red")
            self.save_user_answer(sorted(selected))

        elif qtype == "match":
            # puntuación por par correcto
            hits = 0
            needed = len(self.correct_pairs)
            for q_text, lbl in self.q_labels.items():
                btn = self.match_state.get(q_text)
                if not btn:
                    lbl.config(bg="#fff3cd")  # sin responder
                    continue
                a_text = btn.cget("text")
                if a_text == self.correct_pairs[q_text]:
                    hits += 1
                    lbl.config(bg="#d4edda")
                    btn.config(bg="#d4edda")
                else:
                    lbl.config(bg="#f8d7da")
                    btn.config(bg="#f8d7da")
            correct = (hits == needed)
            self.save_user_answer({k: v.cget("text") for k, v in self.match_state.items()})

        # actualizar marcador
        if correct:
            self.score += 1
        self.answered_current = True
        self.btn_check.config(state="disabled")
        self.update_statusbar()

    def next_question(self):
        if self.current_idx < len(self.questions) - 1:
            self.current_idx += 1
            self.load_current_question()
            self.start_timer()
        else:
            self.show_results()

    def prev_question(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_current_question()
            self.start_timer()

    # -------------------------
    # Resultados
    # -------------------------
    def show_results(self):
        self.stop_timer()
        self.clear_content()
        self.build_topbar()

        card = tk.Frame(self.content, bg="white", bd=1, relief="groove")
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.6)

        total = len(self.questions)
        tk.Label(card, text="Resultados", bg="white",
                 font=("Inter", 16, "bold")).pack(pady=18)
        tk.Label(card, text=f"Puntuación: {self.score} / {total}",
                 bg="white", font=("Inter", 14)).pack(pady=6)

        # Botones
        btns = tk.Frame(card, bg="white")
        btns.pack(pady=18)
        tk.Button(btns, text="Volver al inicio", command=self.show_select_screen,
                  bg="#111827", fg="white", font=("Inter", 11, "bold")).pack(side="left", padx=6)
        tk.Button(btns, text="Reintentar", command=self.retry_same_test,
                  bg="#2563eb", fg="white", font=("Inter", 11, "bold")).pack(side="left", padx=6)

    def retry_same_test(self):
        self.reset_state()
        self.show_question_screen()
