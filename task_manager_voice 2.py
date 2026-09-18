import json
import threading
import time
import os
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import winsound 

try:
    from plyer import notification
except ImportError:
    os.system('pip install plyer')
    from plyer import notification
try:
    import dateparser
except ImportError:
    os.system('pip install dateparser')
    import dateparser
try:
    import pyttsx3
except ImportError:
    os.system('pip install pyttsx3')
    import pyttsx3

TASKS_FILE = 'tasks.json'

def speak_message(message):
    try:
        engine = pyttsx3.init()
        engine.say(message)
        engine.runAndWait()
    except Exception as e:
        print(f"(Speech error: {e})")

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def calculate_status(deadline):
    deadline_dt = None
    try:
        deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            deadline_dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
        except ValueError:
            deadline_dt = dateparser.parse(deadline)
            if not deadline_dt:
                return "Invalid", "-"
    now = datetime.now()
    delta = deadline_dt - now
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "Overdue", "0d 0h 0m"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    if total_seconds < 86400:
        return "Due", f"{hours}h {minutes}m"
    else:
        return "Pending", f"{days}d {hours}h {minutes}m"

def show_notification(tasks):
    urgent_tasks = [t for t in tasks if calculate_status(t['deadline'])[0] in ('Due', 'Overdue')]
    if urgent_tasks:
        details = "\n".join([
            f"{t['task_name']} | Deadline: {t['deadline']} | Status: {calculate_status(t['deadline'])[0]} | Time Left: {calculate_status(t['deadline'])[1]} | Priority: {t['priority']} | Description: {t['description']}"
            for t in urgent_tasks
        ])
        message = f"You have {len(urgent_tasks)} due or overdue task(s):\n{details}"
        try:
            notification.notify(
                title="AI Deadline Management Reminder",
                message=message,
                timeout=15
            )
            speak_message(message)
        except Exception as e:
            print(f"(Notification error: {e})")

def background_reminder():
    notified = set()
    notified_deadline = set()
    notified_exact = set()
    while True:
        tasks = load_tasks()
        now = datetime.now()
        due_tasks = [t for t in tasks if calculate_status(t['deadline'])[0] == 'Due']
        for t in due_tasks:
            key = (t['task_name'], t['deadline'])
            if key not in notified:
                message = (
                    f"Task: {t['task_name']}\n"
                    f"Description: {t['description']}\n"
                    f"Deadline: {t['deadline']}\n"
                    f"Status: {calculate_status(t['deadline'])[0]}\n"
                    f"Time Left: {calculate_status(t['deadline'])[1]}\n"
                    f"Priority: {t['priority']}"
                )
                try:
                    notification.notify(
                        title="AI Deadline Management Reminder",
                        message=message,
                        timeout=15
                    )
                    speak_message(message)
                except Exception as e:
                    print(f"(Notification error: {e})")
                notified.add(key)
        for t in tasks:
            try:
                deadline_dt = dateparser.parse(t['deadline'])
                if deadline_dt:
                    minutes_left = (deadline_dt - now).total_seconds() / 60
                    key_before = (t['task_name'], t['deadline'], 'before_deadline')
                    if 0 < minutes_left <= 2 and key_before not in notified_deadline:
                        message = f"Task '{t['task_name']}' ({t['description']}) is due in {int(minutes_left)} minutes!"
                        speak_message(message)
                        notified_deadline.add(key_before)
                    key_exact = (t['task_name'], t['deadline'], 'exact_deadline')
                    if -1 < minutes_left <= 0 and key_exact not in notified_exact:
                        play_buzzer()
                        message = f"Task '{t['task_name']}' ({t['description']}) deadline is now!"
                        speak_message(message)
                        notified_exact.add(key_exact)
            except Exception:
                continue
        time.sleep(60)

def add_task_gui(tasks, tree):
    task_name = simpledialog.askstring("Task Name", "Enter task name:")
    if not task_name:
        return
    description = simpledialog.askstring("Description", "Enter description:") or ""
    deadline = simpledialog.askstring("Deadline", "Enter deadline (YYYY-MM-DD HH:MM or natural language):")
    if not deadline:
        return
    priority = simpledialog.askstring("Priority", "Enter priority (High/Medium/Low):") or "Medium"
    status, time_left = calculate_status(deadline)
    task = {
        "task_name": task_name,
        "description": description,
        "deadline": deadline,
        "priority": priority,
        "status": status,
        "time_left": time_left
    }
    tasks.append(task)
    save_tasks(tasks)
    update_tree(tree, tasks)
    show_notification(tasks)

def delete_task_gui(tasks, tree):
    selected = tree.selection()
    if not selected:
        messagebox.showinfo("Delete Task", "No task selected.")
        return
    indices = sorted([int(iid) for iid in selected], reverse=True)
    removed_names = []
    for idx in indices:
        removed_names.append(tasks[idx]['task_name'])
        tasks.pop(idx)
    save_tasks(tasks)
    update_tree(tree, tasks)
    messagebox.showinfo("Delete Task", f"Task(s) '{', '.join(removed_names)}' deleted.")

def show_tooltip(widget, text):
    tooltip = tk.Toplevel(widget)
    tooltip.withdraw()
    tooltip.overrideredirect(True)
    label = tk.Label(tooltip, text=text, background="#222831", fg="#EEEEEE", relief='solid', borderwidth=1, font=('Segoe UI', 10))
    label.pack()
    def enter(event):
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + 20
        tooltip.geometry(f"+{x}+{y}")
        tooltip.deiconify()
    def leave(event):
        tooltip.withdraw()
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)

def colorize_rows(tree, tasks):
    for idx, t in enumerate(tasks):
        status, _ = calculate_status(t['deadline'])
        if status == "Overdue":
            tree.item(str(idx), tags=('overdue',))
        elif status == "Due":
            tree.item(str(idx), tags=('due',))
        else:
            tree.item(str(idx), tags=('pending',))
    tree.tag_configure('overdue', background='#ff4d4d', foreground='#23272F')
    tree.tag_configure('due', background='#fff3cd', foreground='#23272F')
    tree.tag_configure('pending', background='#393E46', foreground='#EEEEEE')

def update_tree(tree, tasks):
    tree.delete(*tree.get_children())
    for idx, t in enumerate(tasks):
        # Recalculate status and time_left for up-to-date values
        status, time_left = calculate_status(t['deadline'])
        tree.insert('', 'end', iid=str(idx), values=(
            t['task_name'],
            t['description'],
            t['deadline'],
            status,
            time_left,
            t['priority']
        ))
    colorize_rows(tree, tasks)

def play_buzzer():
    # Play a buzzer sound for about 5 seconds (alternating beeps)
    for _ in range(10):
        winsound.Beep(1500, 250)
        time.sleep(0.25)

def main_gui():
    tasks = load_tasks()
    root = tk.Tk()
    root.title("AI Deadline Management Agent")
    root.geometry("1200x650")
    root.minsize(900, 500)
    root.configure(bg="#23272F")

    # Sidebar
    sidebar = tk.Frame(root, bg="#222831", width=200)
    sidebar.pack(side='left', fill='y')
    tk.Label(sidebar, text="Menu", bg="#222831", fg="#00ADB5", font=("Segoe UI", 18, "bold")).pack(pady=(30, 10))

    btn_frame = tk.Frame(sidebar, bg="#222831")
    btn_frame.pack(pady=10, fill='x')
    def style_btn(btn):
        btn.config(bg="#393E46", fg="#EEEEEE", font=('Segoe UI', 13), bd=0, padx=10, pady=12, relief='flat', cursor="hand2", activebackground="#00ADB5", activeforeground="#23272F")
        btn.bind("<Enter>", lambda e: btn.config(bg="#00ADB5", fg="#23272F"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#393E46", fg="#EEEEEE"))
    add_btn = tk.Button(btn_frame, text="Add Task", command=lambda: add_task_gui_status(tasks, tree))
    del_btn = tk.Button(btn_frame, text="Delete Task", command=lambda: delete_task_gui_status(tasks, tree))
    ref_btn = tk.Button(btn_frame, text="Refresh", command=lambda: refresh_status())
    for btn, tip in [(add_btn, "Add a new task"), (del_btn, "Delete selected task(s)"), (ref_btn, "Reload tasks from file")]:
        style_btn(btn)
        btn.pack(fill='x', padx=24, pady=10)
        show_tooltip(btn, tip)

    # Header
    header = tk.Frame(root, bg="#23272F")
    header.pack(fill='x')
    tk.Label(header, text="AI Deadline Management Agent", bg="#23272F", fg="#00ADB5", font=("Segoe UI", 26, "bold")).pack(pady=18)

    # Main content
    content = tk.Frame(root, bg="#23272F")
    content.pack(fill='both', expand=True, padx=(10, 20), pady=(0, 20))

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background="#23272F", foreground="#EEEEEE", fieldbackground="#23272F", rowheight=32, font=('Segoe UI', 13), borderwidth=0)
    style.map("Treeview", background=[('selected', '#00ADB5')])

    columns = ("Task Name", "Description", "Deadline", "Status", "Time Left", "Priority")
    # MODIFIED: Added selectmode='extended' to allow multi-selection
    tree = ttk.Treeview(content, columns=columns, show='headings', style="Treeview", selectmode='extended')
    for col in columns:
        tree.heading(col, text=col, anchor='center')
        tree.column(col, width=180 if col != "Description" else 300, anchor='center', stretch=True)
    tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)

    # Scrollbar
    vsb = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
    vsb.pack(side='right', fill='y')
    tree.configure(yscrollcommand=vsb.set)

    update_tree(tree, tasks)

    # Details panel
    details = tk.Frame(root, bg="#23272F", width=300)
    details.pack(side='right', fill='y', padx=(0, 10))
    tk.Label(details, text="Task Details", bg="#23272F", fg="#00ADB5", font=("Segoe UI", 16, "bold")).pack(pady=(30, 10))
    desc_var = tk.StringVar()
    deadline_var = tk.StringVar()
    tk.Label(details, textvariable=desc_var, bg="#23272F", fg="#EEEEEE", font=("Segoe UI", 12), wraplength=280, justify='left').pack(pady=10, anchor='w')
    tk.Label(details, textvariable=deadline_var, bg="#23272F", fg="#EEEEEE", font=("Segoe UI", 12)).pack(pady=10, anchor='w')

    def show_details(event):
        selected = tree.selection()
        if selected:
            # For simplicity, details panel shows the first selected item
            idx = int(selected[0])
            if idx < len(tasks):
                t = tasks[idx]
                desc_var.set(f"Description: {t['description']}")
                deadline_var.set(f"Deadline: {t['deadline']}\nPriority: {t['priority']}\nStatus: {calculate_status(t['deadline'])[0]}\nTime Left: {calculate_status(t['deadline'])[1]}")
        else:
            desc_var.set("")
            deadline_var.set("")
    tree.bind("<<TreeviewSelect>>", show_details)

    # Status bar
    status_var = tk.StringVar()
    status_var.set("Ready")
    status_bar = tk.Label(root, textvariable=status_var, bd=1, relief='sunken', anchor='w', font=('Segoe UI', 11), bg="#181A20", fg="#EEEEEE")
    status_bar.pack(side='bottom', fill='x')

    def update_status(msg):
        status_var.set(msg)
        root.after(4000, lambda: status_var.set("Ready"))

    # Update status on actions
    def add_task_gui_status(tasks, tree):
        add_task_gui(tasks, tree)
        update_status("Task added.")
    def delete_task_gui_status(tasks, tree):
        delete_task_gui(tasks, tree)
        update_status("Task(s) deleted.")
    def refresh_status():
        nonlocal tasks
        tasks = load_tasks()
        update_tree(tree, tasks)
        update_status("Tasks refreshed.")

    add_btn.config(command=lambda: add_task_gui_status(tasks, tree))
    del_btn.config(command=lambda: delete_task_gui_status(tasks, tree))
    ref_btn.config(command=refresh_status)

    def on_closing():
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    threading.Thread(target=background_reminder, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    main_gui()