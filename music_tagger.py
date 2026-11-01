"""MusicTagger — graphical batch tag editor, Python 3.9+."""
import io
import queue
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
    from tag_engine import (FIELDS, EXTENSIONS, PATTERNS, read_track, load_cover,
                            existing_cover, output_name, export_track, validate, safe_name)
except ImportError as exc:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror('Нужна установка', f'{exc}\nЗапустите start_windows.bat или установите requirements.txt.')
    raise SystemExit(1)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MusicTagger • Теги и обложки')
        self.geometry('1180x800')
        self.minsize(1000, 740)
        self.tracks = {}
        self.counter = 0
        self.active = None
        self.loading = False
        self.busy = False
        self.events = queue.Queue()
        self.photo = None
        self.vars = {key: tk.StringVar() for key in FIELDS}
        self.parent_folder = tk.StringVar(value=str(Path.home() / 'Music'))
        self.folder_name = tk.StringVar(value='Обработанные песни ' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
        self.pattern = tk.StringVar(value='Исполнитель — Название')
        self.status = tk.StringVar(value='Добавьте песни. Изменения сохранятся только при экспорте копий.')
        self.build()
        for key, var in self.vars.items():
            var.trace_add('write', lambda *_, key=key: self.edit(key))
        self.pattern.trace_add('write', lambda *_: self.refresh_all())
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def build(self):
        style = ttk.Style(self)
        style.configure('Treeview', rowheight=28)
        style.configure('Title.TLabel', font=('Arial', 19, 'bold'))
        main = ttk.Frame(self, padding=16)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='Музыка в порядке', style='Title.TLabel').pack(anchor='w')
        ttk.Label(main, text='Свои названия • общая обложка • новые копии без перекодирования').pack(anchor='w', pady=(3, 12))
        bar = ttk.Frame(main)
        bar.pack(fill='x', pady=(0, 10))
        for text, action in [('Добавить песни', self.add_files), ('Добавить папку', self.add_folder),
                             ('Выделить все', self.select_all), ('Убрать из списка', self.remove)]:
            ttk.Button(bar, text=text, command=action).pack(side='left', padx=(0, 6))
        pane = ttk.Panedwindow(main, orient='horizontal')
        pane.pack(fill='both', expand=True)
        left = ttk.Frame(pane)
        right = ttk.LabelFrame(pane, text='Одна песня: редактируйте поля', padding=12)
        pane.add(left, weight=3)
        pane.add(right, weight=2)
        columns = ('title', 'artist', 'file', 'output', 'status')
        self.tree = ttk.Treeview(left, columns=columns, show='headings', selectmode='extended')
        for col, label, width in zip(columns, ['Название', 'Исполнитель', 'Исходный файл', 'Новое имя', 'Статус'], [170, 130, 150, 180, 130]):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, minwidth=80)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        sx = ttk.Scrollbar(left, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
        ttk.Label(left, text='Ctrl / Cmd — несколько песен; Shift — диапазон.').grid(row=2, column=0, sticky='w', pady=6)
        batch = ttk.Frame(left)
        batch.grid(row=3, column=0, sticky='ew')
        ttk.Button(batch, text='Общие теги…', command=self.batch_dialog).pack(side='left', padx=(0, 6))
        ttk.Button(batch, text='Названия из имён файлов', command=self.names_from_files).pack(side='left')
        self.editor_entries = []
        for row, (key, label) in enumerate(FIELDS.items()):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky='w', pady=4)
            entry = ttk.Entry(right, textvariable=self.vars[key], width=30, state='disabled')
            entry.grid(row=row, column=1, sticky='ew', padx=(10, 0), pady=4)
            self.editor_entries.append(entry)
        right.columnconfigure(1, weight=1)
        ttk.Label(right, text='Поля обновляют выбранную песню сразу.\nДля нескольких песен нажмите «Общие теги…».', wraplength=330).grid(row=8, column=0, columnspan=2, sticky='w', pady=8)
        self.cover_label = ttk.Label(right, text='Обложка', anchor='center')
        self.cover_label.grid(row=9, column=0, columnspan=2, sticky='ew', pady=5)
        coverbar = ttk.Frame(right)
        coverbar.grid(row=10, column=0, columnspan=2, sticky='ew')
        ttk.Button(coverbar, text='Обложка для выделенных…', command=self.choose_cover).pack(side='left')
        ttk.Button(coverbar, text='Удалить', command=lambda: self.set_cover(False)).pack(side='left', padx=5)
        ttk.Button(right, text='Сбросить правки выделенных', command=self.reset).grid(row=11, column=0, columnspan=2, sticky='w', pady=8)
        export = ttk.LabelFrame(main, text='Сохранение всех песен из списка', padding=10)
        export.pack(fill='x', pady=(12, 8))
        ttk.Label(export, text='Куда:').grid(row=0, column=0, sticky='w')
        ttk.Entry(export, textvariable=self.parent_folder).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Button(export, text='Выбрать…', command=self.choose_output).grid(row=0, column=2)
        ttk.Label(export, text='Новая папка:').grid(row=1, column=0, sticky='w', pady=6)
        ttk.Entry(export, textvariable=self.folder_name).grid(row=1, column=1, sticky='ew', padx=8)
        ttk.Label(export, text='Имена файлов:').grid(row=2, column=0, sticky='w')
        ttk.Combobox(export, textvariable=self.pattern, values=list(PATTERNS), state='readonly').grid(row=2, column=1, sticky='ew', padx=8)
        self.export_button = ttk.Button(export, text='Сохранить копии', command=self.export)
        self.export_button.grid(row=1, column=2, rowspan=2, padx=5)
        export.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(main)
        self.progress.pack(fill='x')
        ttk.Label(main, textvariable=self.status, wraplength=1050).pack(anchor='w', pady=(6, 0))

    def selected(self):
        return list(self.tree.selection()) if not self.busy else []

    def add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(title='Выберите песни', filetypes=[('Музыка', '*.mp3 *.flac *.m4a *.ogg *.opus'), ('Все файлы', '*.*')])
        self.add_paths(paths)

    def add_folder(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title='Папка с песнями (без вложенных папок)')
        if folder:
            self.add_paths(sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in EXTENSIONS))

    def add_paths(self, paths):
        known = {t.path for t in self.tracks.values()}
        errors = []
        for path in paths:
            path = Path(path).resolve()
            if path in known:
                continue
            try:
                track = read_track(path)
                self.counter += 1
                iid = str(self.counter)
                self.tracks[iid] = track
                self.tree.insert('', 'end', iid=iid)
                self.refresh(iid)
                known.add(path)
            except Exception as exc:
                errors.append(f'{path.name}: {exc}')
        self.status.set(f'Песен в списке: {len(self.tracks)}. Выберите одну для правки или несколько для общей обложки.')
        if errors:
            messagebox.showwarning('Некоторые файлы не добавлены', '\n'.join(errors)[:5000])

    def refresh(self, iid):
        track = self.tracks[iid]
        values = track.values()
        self.tree.item(iid, values=(values['title'], values['artist'], track.path.name, output_name(track, self.pattern.get()), track.status))

    def refresh_all(self):
        for iid in self.tracks:
            self.refresh(iid)

    def selection_changed(self, _=None):
        ids = self.tree.selection()
        self.active = ids[0] if len(ids) == 1 else None
        self.loading = True
        values = self.tracks[self.active].values() if self.active else {}
        for key, var in self.vars.items():
            var.set(values.get(key, ''))
        for entry in self.editor_entries:
            entry.configure(state='normal' if self.active and not self.busy else 'disabled')
        self.loading = False
        self.show_cover()

    def edit(self, key):
        if self.loading or self.busy or not self.active:
            return
        track = self.tracks[self.active]
        track.changes[key] = self.vars[key].get()
        track.status = 'Изменено'
        self.refresh(self.active)

    def show_cover(self):
        self.photo = None
        self.cover_label.configure(image='', text='Выберите одну песню для просмотра обложки')
        if not self.active:
            return
        try:
            track = self.tracks[self.active]
            data = existing_cover(track.path) if track.cover is None else track.cover
            if data:
                with Image.open(io.BytesIO(data)) as im:
                    im.thumbnail((130, 100))
                    self.photo = ImageTk.PhotoImage(im.copy())
                self.cover_label.configure(image=self.photo, text='')
            else:
                self.cover_label.configure(text='Нет обложки')
        except Exception:
            self.cover_label.configure(text='Не удалось показать обложку')

    def select_all(self):
        if not self.busy:
            self.tree.selection_set(self.tree.get_children())

    def remove(self):
        for iid in self.selected():
            self.tree.delete(iid)
            del self.tracks[iid]
        self.selection_changed()

    def reset(self):
        for iid in self.selected():
            track = self.tracks[iid]
            track.changes.clear()
            track.cover = None
            track.status = 'Без изменений'
            self.refresh(iid)
        self.selection_changed()

    def names_from_files(self):
        for iid in self.selected():
            track = self.tracks[iid]
            track.changes['title'] = track.path.stem
            track.status = 'Изменено'
            self.refresh(iid)
        self.selection_changed()

    def choose_cover(self):
        if not self.selected():
            messagebox.showinfo('Выбор песен', 'Сначала выделите песни в списке.')
            return
        path = filedialog.askopenfilename(title='Одна обложка для выделенных песен', filetypes=[('Изображения', '*.jpg *.jpeg *.png *.webp'), ('Все файлы', '*.*')])
        if path:
            try:
                self.set_cover(load_cover(path))
            except Exception as exc:
                messagebox.showerror('Не удалось открыть обложку', str(exc))

    def set_cover(self, data):
        ids = self.selected()
        for iid in ids:
            self.tracks[iid].cover = data
            self.tracks[iid].status = 'Изменено'
            self.refresh(iid)
        self.show_cover()
        self.status.set(f'Обложка {"назначена" if data else "удалена"} для {len(ids)} песен. Сохраните копии для применения.')

    def batch_dialog(self):
        ids = self.selected()
        if not ids:
            messagebox.showinfo('Выбор песен', 'Сначала выделите песни в списке.')
            return
        dialog = tk.Toplevel(self)
        dialog.title(f'Общие теги • {len(ids)} песен')
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Изменятся только отмеченные поля.\nОтмеченное пустое поле удалит соответствующий тег.').grid(row=0, column=0, columnspan=2, pady=(0, 12))
        checks, values = {}, {}
        for row, (key, label) in enumerate(FIELDS.items(), 1):
            checks[key] = tk.BooleanVar()
            values[key] = tk.StringVar()
            ttk.Checkbutton(frame, text=label, variable=checks[key]).grid(row=row, column=0, sticky='w', pady=4)
            ttk.Entry(frame, textvariable=values[key], width=35).grid(row=row, column=1, padx=8)
        def apply():
            changes = {key: values[key].get().strip() for key in FIELDS if checks[key].get()}
            try:
                validate(changes)
            except ValueError as exc:
                messagebox.showerror('Проверьте значения', str(exc), parent=dialog)
                return
            for iid in ids:
                self.tracks[iid].changes.update(changes)
                if changes:
                    self.tracks[iid].status = 'Изменено'
                self.refresh(iid)
            dialog.destroy()
            self.selection_changed()
        ttk.Button(frame, text='Применить к выделенным', command=apply).grid(row=9, column=0, columnspan=2, pady=(12, 0))

    def choose_output(self):
        if not self.busy:
            folder = filedialog.askdirectory(title='Куда поместить новую папку')
            if folder:
                self.parent_folder.set(folder)

    def export(self):
        if self.busy or not self.tracks:
            return
        folder_name = self.folder_name.get().strip()
        if not folder_name or safe_name(folder_name) != folder_name:
            messagebox.showerror('Имя папки', 'Укажите простое имя папки без символов / \\ : * ? " < > | и точек в конце.')
            return
        if not self.parent_folder.get().strip():
            messagebox.showerror('Папка', 'Выберите папку назначения.')
            return
        for track in self.tracks.values():
            try:
                validate(track.changes)
            except ValueError as exc:
                messagebox.showerror('Проверьте теги', f'{track.path.name}\n{exc}')
                return
        target = Path(self.parent_folder.get()).expanduser() / folder_name
        pattern = self.pattern.get()
        jobs = list(self.tracks.items())
        self.busy = True
        self.export_button.configure(state='disabled')
        self.selection_changed()
        self.progress.configure(value=0, maximum=len(jobs))
        self.status.set('Сохраняю копии…')
        def worker():
            errors = []
            for index, (iid, track) in enumerate(jobs, 1):
                try:
                    path = export_track(track, target, pattern)
                    self.events.put(('progress', iid, index, f'Готово: {path.name}'))
                except Exception as exc:
                    errors.append(f'{track.path.name}: {exc}')
                    self.events.put(('progress', iid, index, f'Ошибка: {exc}'))
            self.events.put(('done', target, errors, len(jobs)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'progress':
                    _, iid, count, status = event
                    self.tracks[iid].status = status
                    self.refresh(iid)
                    self.progress.configure(value=count)
                    self.status.set(status)
                else:
                    _, target, errors, total = event
                    self.busy = False
                    self.export_button.configure(state='normal')
                    self.selection_changed()
                    summary = f'Сохранено {total - len(errors)} из {total}.\nПапка: {target}'
                    self.status.set(summary.replace('\n', ' '))
                    if errors:
                        messagebox.showwarning('Сохранение завершено с ошибками', summary + '\n\n' + '\n'.join(errors)[:5000])
                    else:
                        messagebox.showinfo('Готово', summary)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Идёт сохранение', 'Дождитесь окончания сохранения копий.')
            return
        if any(t.changes or t.cover is not None for t in self.tracks.values()):
            if not messagebox.askokcancel('Закрыть приложение?', 'Правки хранятся в этой сессии. Если вы ещё не сохранили копии, они будут потеряны. Закрыть?'):
                return
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
