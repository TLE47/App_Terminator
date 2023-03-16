# Import required libraries
import os
import plistlib
import tkinter as tk
from tkinter import ttk, filedialog
import psutil
import subprocess
import concurrent.futures
from tqdm import tqdm

# Set the allowed apps file path
ALLOWED_APPS_FILE = "allowed_apps.txt"

# Load the allowed apps from the file
def load_allowed_apps():
    if not os.path.exists(ALLOWED_APPS_FILE):
        return set()

    with open(ALLOWED_APPS_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())

# Save the allowed apps to the file
def save_allowed_apps(apps):
    with open(ALLOWED_APPS_FILE, "w") as f:
        for app in apps:
            f.write(app + "\n")

# Get the helper apps for a give bundle path
def get_helper_apps(bundle_path):
    info_plist = os.path.join(bundle_path, "Contents", "Info.plist")
    if not os.path.exists(info_plist):
        return []

    with open(info_plist, "rb") as f:
        plist = plistlib.load(f)

    helpers = []

    if "CFBundleDocumentTypes" in plist:
        for doc_type in plist["CFBundleDocumentTypes"]:
            if "NSDocumentClass" in doc_type:
                helpers.append(doc_type["NSDocumentClass"])

    if "CFBundleServices" in plist:
        for service in plist["CFBundleServices"]:
            if "NSExecutable" in service:
                helpers.append(service["NSExecutable"])

    return helpers

# Terminate apps that are not in the allowed app list
def terminate_apps(allowed_apps):
    allowed_apps_basenames = {os.path.splitext(os.path.basename(app))[0] for app in allowed_apps}
    running_processes = [proc for proc in psutil.process_iter(["name", "pid"]) if proc.info["pid"] > 0]
    
    for process in tqdm(running_processes, desc="Terminating Apps", unit="app"):
        if process.info["name"] not in allowed_apps_basenames:
            try:
                cmd = f'osascript -e \'quit app "{process.info["name"]}"\' >/dev/null 2>&1'
                subprocess.call(cmd, shell=True)
            except:
                pass

# Terminate a specific app by its process name
def terminate_app(process_name):
    try:
        cmd = f'osascript -e \'quit app "{process_name}"\' >/dev/null 2>&1'
        subprocess.call(cmd, shell=True, timeout=5)
        return f"Terminated: {process_name}"
    except subprocess.TimeoutExpired:
        return f"Timeout: {process_name}"
    except:
        return f"Failed to terminate: {process_name}"

# Define the main App class, inheriting from tk.Tk
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Set the window title and size
        self.title("App Terminator")
        self.geometry("250x500")

        # Load the allowed apps and create the widgets
        self.allowed_apps = load_allowed_apps()
        self.create_widgets()

        # Create progress bar and status labels
        self.progress_label_var = tk.StringVar()
        self.progress_label_var.set("Progress:")
        self.progress_label = tk.Label(self, textvariable=self.progress_label_var)
        self.progress_label.pack(pady=5)

        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(
            self, length=200, mode="determinate", variable=self.progress_var
        )
        self.progressbar.pack(pady=5)

        self.status_text = tk.StringVar()
        self.status_label = tk.Label(self, textvariable=self.status_text)
        self.status_label.pack(pady=5)

        # Create a status box to display termination status
        self.status_box = tk.Text(self, height=10, state="disabled")
        self.status_box.pack(pady=5, expand=True, fill=tk.BOTH)

    # Create the UI widgets (treeview, button, etc.)
    def create_widgets(self):
        self.tree_frame = tk.Frame(self)
        self.tree_frame.pack(expand=True, fill=tk.BOTH)

        self.tree = ttk.Treeview(self.tree_frame)
        self.tree.heading("#0", text="Allowed Apps")
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        for app in self.allowed_apps:
            self.tree.insert("", tk.END, text=app)
        
        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        add_button = tk.Button(self, text="Add", command=self.add_app)
        add_button.pack(pady=5)

        delete_button = tk.Button(self, text="Delete", command=self.delete_app)
        delete_button.pack(pady=5)

        terminate_button = tk.Button(
            self, text="Terminate Apps", command=self.terminate_apps_button
        )
        terminate_button.pack(pady=5)
        
        self.auto_close_var = tk.BooleanVar()
        self.auto_close_check = tk.Checkbutton(
            self, text="Auto-close", variable=self.auto_close_var
        )
        self.auto_close_check.pack(pady=5)

    # Add an app to the allowed apps list
    def add_app(self):
        app_path = filedialog.askopenfilename(
            title="Select App",
            filetypes=(("Application", "*.app"), ("All Files", "*.*")),
        )

        if not app_path:
            return

        app_name = os.path.basename(app_path)
        self.allowed_apps.add(app_name)
        save_allowed_apps(self.allowed_apps)

        self.tree.insert("", tk.END, text=app_name)

    # Delete the selected app from the allowed apps list
    def delete_app(self):
        selected_items = self.tree.selection()

        for item in selected_items:
            app_name = self.tree.item(item, "text")
            self.allowed_apps.remove(app_name)
            self.tree.delete(item)

        save_allowed_apps(self.allowed_apps)

    # Terminate the apps when the terminatae button is clicked
    def terminate_apps_button(self):
        self.after(10, self.terminate_apps_in_gui)

        if self.auto_close_var.get():
            self.after(1000, self.destroy)

    # Terminate the apps and update the UI accordingly
    def terminate_apps_in_gui(self):
        script_process_name = os.path.splitext(os.path.basename(__file__))[0]
        allowed_apps_basenames = {os.path.splitext(os.path.basename(app))[0] for app in self.allowed_apps}
        allowed_apps_basenames.add(script_process_name)

        helper_apps = set()
        for app in self.allowed_apps:
            app_path = os.path.join("/Applications", app)
            helper_apps.update(get_helper_apps(app_path))

        running_processes = [
            proc for proc in psutil.process_iter(["name", "pid"]) if proc.info["pid"] > 0
        ]
        total_processes = len(running_processes)
        self.progress_var.set(0)
        self.progressbar["maximum"] = total_processes

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_process = {executor.submit(terminate_app, process.info["name"]): process for process in running_processes if (process.info["name"] not in allowed_apps_basenames and process.info["name"] not in helper_apps)}

            for i, future in enumerate(concurrent.futures.as_completed(future_to_process)):
                process = future_to_process[future]
                try:
                    status_msg = future.result()
                except Exception as exc:
                    status_msg = f"Failed to terminate {process.info['name']}: {exc}"

                self.status_text.set(status_msg)
                self.status_box.configure(state="normal")
                self.status_box.insert(tk.END, status_msg + "\n")
                self.status_box.configure(state="disabled")
                self.status_box.see(tk.END)

                self.progress_var.set(i + 1)
                self.update_idletasks()
        self.progress_label_var.set("Done!")

# Initialize and run the app
if __name__ == "__main__":
    app = App()
    app.mainloop()
    
