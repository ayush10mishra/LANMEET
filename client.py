import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog, Frame, Label, Listbox, Canvas
from tkinter import ttk
import cv2
import pyaudio
import numpy as np
import pickle
import struct
from PIL import Image, ImageTk
import io
import mss
import os
import base64
import hashlib
import time 

# --- Configuration ---
SERVER_HOST = None
TCP_PORT = 3478
UDP_PORT = 6734
# ---------------------

# --- Audio Config ---
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
# --------------------

# --- Unified "Blue Tech Dark Mode" Style Configuration ---
BG_COLOR = "#0D1117"
FRAME_BG = "#161B22"
CHAT_BG = "#161B22"
LIST_BG = "#161B22"
LOG_BG = "#161B22"
FG_COLOR = "#EBEBEB"
FG_DARKER = "#BDC1C6"
ACCENT_COLOR = "#5B9CFF"      # Vibrant Blue
ACCENT_DARK = "#1A73E8"       # Deep Blue (Hover/Active)
BTN_SUCCESS = "#34C444"       # Vibrant Green
BTN_DANGER = "#FF6B6B"        # Clean Red
BTN_DANGER_ACTIVE = "#FF9999" # Lighter Red on Active
BTN_BG = "#33363B"            # Button Background
BTN_BG_ACTIVE = "#44474C"     # Button Hover Background
AVATAR_COLORS = ["#FF6B6B", "#FFD97D", "#8DD3C7", "#5B9CFF", "#BB86FC", "#FFB6C1", "#A52A2A", "#8A2BE2"] 
# --------------------------------------------------------
class ServerIPDialog(simpledialog.Dialog):
    """Custom dialog to get server IP address."""
    
    def __init__(self, parent, title="Server Connection"):
        self.server_ip = None
        super().__init__(parent, title)
    
    def body(self, master):
        """Create dialog body with IP input field."""
        master.configure(bg=BG_COLOR)
        
        ttk.Label(master, text="Enter Server IP Address:", 
                 font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(10, 20), padx=20, sticky='w')
        
        ttk.Label(master, text="Server IP:", 
                 font=("Arial", 10)).grid(row=1, column=0, sticky='w', padx=20, pady=5)
        
        self.ip_entry = ttk.Entry(master, font=("Arial", 11), width=20)
        self.ip_entry.grid(row=1, column=1, pady=5, padx=(0, 20), sticky='ew')
        self.ip_entry.insert(0, "192.168.1.")
        
        ttk.Label(master, text="Examples: 192.168.1.100 or 10.0.0.5", 
                 font=("Arial", 9)).grid(row=2, column=0, columnspan=2, 
                                                                pady=(5, 10), padx=20, sticky='w')
        
        master.grid_columnconfigure(1, weight=1)
        return self.ip_entry

    def validate(self):
        """Validate IP address format."""
        ip = self.ip_entry.get().strip()
        
        if not ip:
            messagebox.showerror("Invalid Input", "Please enter an IP address.", parent=self)
            return False
        
        parts = ip.split('.')
        if len(parts) != 4:
            messagebox.showerror("Invalid IP", "IP address must have 4 parts separated by dots.\nExample: 192.168.1.100", parent=self)
            return False
        
        try:
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    raise ValueError
        except ValueError:
            messagebox.showerror("Invalid IP", "Each part of the IP must be a number between 0 and 255.", parent=self)
            return False
        
        self.server_ip = ip
        return True
    
    def apply(self):
        pass


class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1100x750")
        self.root.configure(bg=BG_COLOR)
        self.root.minsize(900, 600)

        # --- Initial Setup ---
        if not self._get_user_info():
            self.root.destroy()
            return
            
        self.root.title(f"LANMeet - {self.username}")
        self._initialize_state_variables()
        self._setup_styles()
        self._setup_gui()
        
        # --- Start Connection ---
        self.root.after(100, self._connect_to_server)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # =================================================================================
    #   1. INITIALIZATION AND STATE
    # =================================================================================

    def _get_user_info(self):
        global SERVER_HOST
        ip_dialog = ServerIPDialog(self.root)
        
        if not ip_dialog.server_ip:
            return False
        
        SERVER_HOST = ip_dialog.server_ip
        self.server_host = SERVER_HOST
        
        try:
            self.username = simpledialog.askstring("Username", "Please enter your username:", parent=self.root)
        except Exception:
            self.username = None
            
        return bool(self.username)

    def _initialize_state_variables(self):
        # Media State
        self.video_enabled = tk.BooleanVar(value=False)
        self.audio_enabled = tk.BooleanVar(value=True)
        self.screen_sharing_active = threading.Event()
        self.is_presenting = False
        
        # GUI State
        self.is_side_panel_open = False
        self.screen_presenter_name = tk.StringVar(value="No one is presenting")
        self.my_video_label = None 
        self.screen_share_label = None
        
        # Data/Network State
        self.video_frames = {} 
        self.is_connected = threading.Event()
        self.tcp_socket = None
        self.udp_socket = None
        self.server_udp_addr = (self.server_host, UDP_PORT)
        self.tcp_lock = threading.Lock()
        
        # Media Devices
        self.camera = None
        self.p_audio = pyaudio.PyAudio()
        self.audio_stream_in = None
        self.audio_stream_out = None
        self._camera_lock = threading.Lock()
        
        # File Transfer State
        self._file_log_entries = [] 
        self.active_file_transfers = set()
        self._temp_filepath_store = {}

    # =================================================================================
    #   2. GUI SETUP AND DISPLAY MANAGEMENT
    # =================================================================================

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".", background=BG_COLOR, foreground=FG_COLOR, fieldbackground=FRAME_BG, borderwidth=0, lightcolor=FRAME_BG, darkcolor=FRAME_BG)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Arial", 10))
        style.configure("TFrame", background=BG_COLOR)
        style.configure("Control.TButton", background=BTN_BG, foreground=FG_COLOR, borderwidth=0, relief=tk.FLAT, font=("Arial", 10, "bold"), padding=8)
        style.map("Control.TButton", background=[('active', BTN_BG_ACTIVE), ('disabled', FRAME_BG)], foreground=[('disabled', FG_DARKER)])
        style.configure("Red.TButton", background=BTN_DANGER, foreground="white", borderwidth=0, relief=tk.FLAT, font=("Arial", 10, "bold"), padding=8)
        style.map("Red.TButton", background=[('active', BTN_DANGER_ACTIVE)])
        style.configure("Small.TButton", background=BTN_BG, foreground=FG_COLOR, relief=tk.FLAT, padding=6) 
        style.map("Small.TButton", background=[('active', BTN_BG_ACTIVE)])
        style.configure("Blue.TButton", background=ACCENT_COLOR, foreground="white", borderwidth=0, relief=tk.FLAT, font=("Arial", 10, "bold"), padding=8)
        style.map("Blue.TButton", background=[('active', ACCENT_DARK)])
        style.configure("TPanedWindow", background=BG_COLOR)
        style.configure("TEntry", fieldbackground=LIST_BG, foreground=FG_COLOR, borderwidth=0, relief=tk.FLAT, insertbackground=FG_COLOR, padding=8)
        style.configure("TNotebook", background=BG_COLOR, borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background=FRAME_BG, foreground=FG_DARKER, padding=[10, 5], font=("Arial", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", BG_COLOR), ("active", BTN_BG_ACTIVE)], foreground=[("selected", ACCENT_COLOR), ("active", FG_COLOR)])

    def _setup_gui(self):
        self._create_main_frames()
        self._create_control_bar_widgets()
        self._create_side_panel_widgets()
        self.root.after(10, lambda: self.add_user_feed(self.username, is_local=True)) 

    def _create_main_frames(self):
        # Bottom Bar
        self.control_bar = ttk.Frame(self.root, style="TFrame", padding=(10, 10))
        self.control_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Main Content Area
        self.main_content_area = ttk.Frame(self.root)
        self.main_content_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Side Panel (Chat/Members/Files) - Initially hidden
        self.side_panel = ttk.Frame(self.main_content_area, width=300)
        self.side_panel.pack_forget() 
        
        # Main Screen (Video/Screen Share)
        self.video_screen_area = ttk.Frame(self.main_content_area)
        self.video_screen_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Sidebar for presenter view
        self.presenter_video_sidebar = ttk.Frame(self.video_screen_area)
        self.presenter_video_sidebar.pack_forget() 
        
        # Screen Share Label (Hidden initially)
        self.screen_share_label = Label(self.video_screen_area, bg='black')
        self.screen_share_label.pack_forget() 
        
        # Video Grid (Active initially)
        self.avatar_grid_frame = ttk.Frame(self.video_screen_area)
        self.avatar_grid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.avatar_grid_frame.bind("<Configure>", self.update_layout_grid)

    def _create_control_bar_widgets(self):
        bar_left = ttk.Frame(self.control_bar); bar_left.pack(side=tk.LEFT, expand=True, anchor='w', padx=10)
        bar_center = ttk.Frame(self.control_bar); bar_center.pack(side=tk.LEFT, expand=True)
        bar_right = ttk.Frame(self.control_bar); bar_right.pack(side=tk.LEFT, expand=True, anchor='e', padx=10)
        
        # Center Buttons (Media Controls)
        self.audio_btn = self._create_ttk_button(bar_center, 'Mic On', "Control.TButton", self.on_toggle_audio_click); self.audio_btn.pack(side=tk.LEFT, padx=5)
        self.video_btn = self._create_ttk_button(bar_center, 'Video Off', "Red.TButton", self.on_toggle_video_click); self.video_btn.pack(side=tk.LEFT, padx=5)
        self.share_btn = self._create_ttk_button(bar_center, 'Share', "Control.TButton", self.start_screen_share); self.share_btn.pack(side=tk.LEFT, padx=5)
        self.end_call_btn = self._create_ttk_button(bar_center, 'End Call', "Red.TButton", lambda: self.on_closing(force=False)); self.end_call_btn.pack(side=tk.LEFT, padx=10)
        
        # Right Buttons (Side Panel Toggles)
        self.members_btn = self._create_ttk_button(bar_right, 'Members', "Control.TButton", lambda: self.toggle_side_panel('members')); self.members_btn.pack(side=tk.LEFT, padx=5)
        self.chat_btn = self._create_ttk_button(bar_right, 'Chat', "Control.TButton", lambda: self.toggle_side_panel('chat')); self.chat_btn.pack(side=tk.LEFT, padx=5)
        self.file_btn = self._create_ttk_button(bar_right, 'Files', "Control.TButton", lambda: self.toggle_side_panel('files')); self.file_btn.pack(side=tk.LEFT, padx=5)

    def _create_side_panel_widgets(self):
        # Side Panel Close Button
        self.side_panel_close_btn = self._create_ttk_button(self.side_panel, 'X', "Control.TButton", lambda: self.toggle_side_panel(None))
        self.side_panel_close_btn.pack(side=tk.TOP, anchor='e', pady=5, padx=5)
        
        # Notebook (Tabbed Interface)
        self.notebook = ttk.Notebook(self.side_panel, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=0, padx=0)
        
        # --- Chat Tab ---
        chat_tab = ttk.Frame(self.notebook, padding=(5, 10))
        self.notebook.add(chat_tab, text="Chat")
        self.chat_area = scrolledtext.ScrolledText(chat_tab, height=10, state='disabled', bg=CHAT_BG, fg=FG_COLOR, font=("Consolas", 10), relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=FRAME_BG)
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        chat_entry_frame = ttk.Frame(chat_tab, padding=(0, 5, 0, 0)); chat_entry_frame.pack(fill=tk.X)
        self.chat_input = ttk.Entry(chat_entry_frame, font=("Arial", 10))
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self._send_chat_message_event)
        self.send_chat_btn = self._create_ttk_button(chat_entry_frame, 'Send', "Small.TButton", self._send_chat_message_event); self.send_chat_btn.pack(side=tk.RIGHT, padx=(5,0))
        
        # --- Members Tab ---
        member_tab = ttk.Frame(self.notebook, padding=(5, 10))
        self.notebook.add(member_tab, text="Members")
        self.member_listbox = Listbox(member_tab, height=5, bg=LIST_BG, fg=FG_COLOR, selectbackground=ACCENT_COLOR, font=("Arial", 10), relief=tk.FLAT, borderwidth=0, highlightthickness=0)
        self.member_listbox.pack(fill=tk.BOTH, expand=True)
        
        # --- Files Tab ---
        file_tab = ttk.Frame(self.notebook, padding=(5, 10))
        self.notebook.add(file_tab, text="Files")
        self.file_send_btn = self._create_ttk_button(file_tab, 'Send File', "Blue.TButton", self._select_file_to_send)
        self.file_send_btn.pack(fill=tk.X, pady=5)
        ttk.Label(file_tab, text="File Transfer Log", font=("Arial", 10, "bold"), foreground=ACCENT_COLOR).pack(pady=(10, 5), anchor='w')
        self.file_log_area = scrolledtext.ScrolledText(file_tab, height=8, state='disabled', bg=CHAT_BG, fg=FG_COLOR, font=("Consolas", 9), relief=tk.FLAT, borderwidth=0, highlightthickness=1, highlightbackground=FRAME_BG)
        self.file_log_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

    def _create_ttk_button(self, parent, button_text, style, command):
        return ttk.Button(parent, text=button_text, style=style, command=command)

    def toggle_side_panel(self, tab_to_open):
        if not hasattr(self, 'notebook'): return
        
        current_tab_index = -1
        if self.is_side_panel_open:
            try: current_tab_index = self.notebook.index(self.notebook.select())
            except tk.TclError: pass

        # Determine if the clicked button should close the panel
        should_close = self.is_side_panel_open and (
           not tab_to_open or
           (tab_to_open == 'chat' and current_tab_index == 0) or
           (tab_to_open == 'members' and current_tab_index == 1) or
           (tab_to_open == 'files' and current_tab_index == 2))

        if should_close:
            self.side_panel.pack_forget()
            self.is_side_panel_open = False
        else:
            try:
                if tab_to_open == 'chat': self.notebook.select(0)
                elif tab_to_open == 'members': self.notebook.select(1)
                elif tab_to_open == 'files': self.notebook.select(2)
            except tk.TclError:
                pass
            
            if not self.is_side_panel_open:
                self.side_panel.pack(side=tk.RIGHT, fill=tk.Y, before=self.video_screen_area)
                self.is_side_panel_open = True
            
    def add_user_feed(self, username, is_local=False):
        if username in self.video_frames: return
        self.video_frames[username] = {
            'label': None, 'avatar': None, 'container': None, 
            'is_local': is_local, 'remote_video_status': False 
        }
        self.update_layout_grid()

    def remove_user_feed(self, username):
        if username in self.video_frames:
            details = self.video_frames.pop(username)
            container = details.get('container')
            def _destroy():
                try:
                    if container and container.winfo_exists():
                        container.destroy()
                except tk.TclError: pass
            if self.root.winfo_exists():
                self.root.after(0, _destroy)
            self.update_layout_grid()
            
    def update_layout_grid(self, event=None):
        if not self.root.winfo_exists(): return
        try:
            # Clear existing widgets from the old parent
            for widget in list(self.presenter_video_sidebar.winfo_children()): widget.destroy()
            for widget in list(self.avatar_grid_frame.winfo_children()): 
                if widget.winfo_ismapped(): widget.grid_forget()

            # Determine parent frame and display parameters
            if self.is_presenting:
                parent_frame = self.presenter_video_sidebar
                parent_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
                avatar_size = 120
                video_height_ratio = 0.75
            else:
                parent_frame = self.avatar_grid_frame
                parent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
                avatar_size = 240
                video_height_ratio = 0.75
                
            video_height = int(avatar_size * video_height_ratio)
            
            # Recreate and map widgets
            user_list = sorted(list(self.video_frames.keys()))
            containers_to_grid = []
            
            for username in user_list:
                details = self.video_frames[username]
                container = details.get('container')
                
                # Check if container needs creation or destruction (due to parent change)
                if container and container.winfo_exists() and container.master != parent_frame:
                    container.destroy(); container = None
                if not container or not container.winfo_exists():
                    container = ttk.Frame(parent_frame)
                    avatar_canvas = self._create_avatar(container, username, avatar_size)
                    video_label = Label(container, bg='black', width=avatar_size, height=video_height)
                    name_text = f"{username}" + (" (You)" if details['is_local'] else "")
                    name_label = ttk.Label(container, text=name_text, anchor="center", font=("Arial", 10 if not self.is_presenting else 8))
                    
                    # Pack widgets within the container (always use pack here for internal layout)
                    avatar_canvas.pack(fill=tk.BOTH, expand=True)
                    video_label.pack(fill=tk.BOTH, expand=True); video_label.pack_forget()
                    name_label.pack(fill=tk.X, pady=(2,0))

                    # Update state
                    details.update({'container': container, 'label': video_label, 'avatar': avatar_canvas, 'name_label': name_label})
                    if details['is_local']: self.my_video_label = video_label
                    
                containers_to_grid.append(container)
                
                # Update visibility
                is_video_on = details.get('remote_video_status', False) if not details['is_local'] else self.video_enabled.get()
                self._update_video_frame_visibility(username, show_video=is_video_on)

            # Grid layout logic for non-presenting view
            if not self.is_presenting:
                frame_width = parent_frame.winfo_width()
                if frame_width <= 1: frame_width = 600
                max_cols = max(1, frame_width // (avatar_size + 10))
                num_rows = (len(containers_to_grid) + max_cols - 1) // max_cols
                
                for c in range(max_cols): parent_frame.grid_columnconfigure(c, weight=1)
                for r in range(num_rows): parent_frame.grid_rowconfigure(r, weight=1)
                
                for i, container in enumerate(containers_to_grid):
                    row, col = i // max_cols, i % max_cols
                    if container.winfo_exists():
                        container.grid(row=row, column=col, padx=5, pady=5, sticky="")
            else:
                # Presenter sidebar uses pack (already done in the loop)
                pass

        except Exception as e:
            print(f"Error in update_layout_grid: {e}")

    def _create_avatar(self, parent, username, size):
        container = Frame(parent, bg=BG_COLOR, width=size, height=size)
        container.pack_propagate(False)
        hash_val = int(hashlib.md5(username.encode()).hexdigest(), 16)
        color = AVATAR_COLORS[hash_val % len(AVATAR_COLORS)]
        canvas = Canvas(container, width=size, height=size, bg=BG_COLOR, highlightthickness=0)
        canvas.pack()
        circle_size = size * 0.8
        pad = size * 0.1
        canvas.create_oval(pad, pad, pad + circle_size, pad + circle_size, fill=color, outline="")
        initial = username[0].upper() if username else "?"
        canvas.create_text(size/2, size/2, text=initial, font=("Arial", size // 3, "bold"), fill="white")
        return container
        
    def _update_video_frame_visibility(self, username, show_video):
        if username not in self.video_frames: return
        widgets = self.video_frames[username]
        label = widgets.get('label')
        avatar = widgets.get('avatar')
        def _update():
            try:
                if not (label and avatar and label.winfo_exists() and avatar.winfo_exists()): return
                if show_video:
                    avatar.pack_forget()
                    label.pack(fill=tk.BOTH, expand=True)
                else:
                    label.pack_forget()
                    avatar.pack(fill=tk.BOTH, expand=True)
            except tk.TclError as e:
                print(f"TclError in _update_video_frame_visibility: {e}")
        if self.root.winfo_exists(): self.root.after(0, _update)

    def _update_video_display(self, label_widget, imgtk):
        try:
            if label_widget and label_widget.winfo_exists():
                label_widget.imgtk = imgtk 
                label_widget.config(image=imgtk)
        except tk.TclError: pass
            
    # =================================================================================
    #   3. CONNECTION AND CLEANUP
    # =================================================================================

    def _connect_to_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.server_host, TCP_PORT))
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', 0))
            my_udp_port = self.udp_socket.getsockname()[1]
            join_message = f"JOIN:{self.username}:{my_udp_port}"
            self.tcp_socket.send(join_message.encode('utf-8'))
            self.is_connected.set()
            self.add_log_message(f"Connected to {self.server_host} as '{self.username}'")
            
            self._start_media_devices()
            
            threading.Thread(target=self._run_tcp_receiver, daemon=True, name="TCP-Recv").start()
            threading.Thread(target=self._run_udp_receiver, daemon=True, name="UDP-Recv").start()
            threading.Thread(target=self._run_video_sender, daemon=True, name="Vid-Send").start()
            threading.Thread(target=self._run_audio_sender, daemon=True, name="Aud-Send").start()
        except Exception as e:
            if self.root.winfo_exists():
                messagebox.showerror("Connection Failed", f"Could not connect to server at {self.server_host}:{TCP_PORT}\n\nError: {e}\n\nPlease check:\n- Server IP address is correct\n- Server is running\n- You're on the same network")
                self.on_closing(force=True)

    def _start_media_devices(self):
        # Audio Setup
        try:
            self.audio_stream_in = self.p_audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            self.audio_stream_out = self.p_audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
            self.audio_enabled.set(True)
            self.add_log_message("Audio devices started.")
            if hasattr(self, 'audio_btn') and self.audio_btn.winfo_exists():
                self.audio_btn.config(text="Mic On", style="Control.TButton")
        except Exception as e:
            self.add_log_message(f"[WARNING] Audio failed ({e}). You will be muted.")
            self.audio_enabled.set(False)
            if hasattr(self, 'audio_btn') and self.audio_btn.winfo_exists():
                self.audio_btn.config(text="No Mic", style="Red.TButton", state='disabled')
        
        # Camera Check
        try:
            test_cam = cv2.VideoCapture(0)
            if not test_cam.isOpened(): raise Exception("Camera not found")
            test_cam.release()
            self.add_log_message("Camera found. Video is ready.")
            self.video_enabled.set(False) 
            if hasattr(self, 'video_btn') and self.video_btn.winfo_exists():
                self.video_btn.config(text="Video Off", style="Red.TButton", state='normal')
        except Exception as e:
            self.add_log_message(f"[WARNING] No camera found ({e}). Video disabled.")
            self.video_enabled.set(False)
            self.camera = None
            if hasattr(self, 'video_btn') and self.video_btn.winfo_exists():
                self.video_btn.config(text="No Cam", style="Red.TButton", state='disabled')
            self._update_video_frame_visibility(self.username, show_video=False)

    def _trigger_shutdown(self):
        if self.root.winfo_exists(): self.on_closing(force=True)

    def on_closing(self, force=False):
        if not force and self.is_connected.is_set():
            if not messagebox.askyesno("Quit", "Are you sure you want to quit?"):
                return
        
        self.is_connected.clear()
        self.screen_sharing_active.clear()
        
        # Stop Media
        self._stop_camera_capture()
        if self.audio_stream_in: 
            try: self.audio_stream_in.stop_stream(); self.audio_stream_in.close()
            except Exception: pass
        if self.audio_stream_out: 
            try: self.audio_stream_out.stop_stream(); self.audio_stream_out.close()
            except Exception: pass
        if self.p_audio:
            try: self.p_audio.terminate()
            except Exception: pass

        # Close Sockets
        if self.tcp_socket:
            try: self._send_tcp_message({'type': 'LEAVE'}) # Notify server
            except Exception: pass
            try: self.tcp_socket.shutdown(socket.SHUT_RDWR); self.tcp_socket.close()
            except Exception: pass
        if self.udp_socket: 
            try: self.udp_socket.close()
            except Exception: pass
        
        self._temp_filepath_store.clear()
        
        if self.root.winfo_exists(): self.root.destroy()
        
    # =================================================================================
    #   4. MEDIA AND SHARING CONTROLS
    # =================================================================================

    def on_toggle_audio_click(self):
        self.audio_enabled.set(not self.audio_enabled.get())
        is_enabled = self.audio_enabled.get()
        self.add_log_message(f"Audio {'enabled' if is_enabled else 'muted'}")
        if hasattr(self, 'audio_btn') and self.audio_btn.winfo_exists():
            if is_enabled:
                self.audio_btn.config(text="Mic On", style="Control.TButton")
            else:
                self.audio_btn.config(text="Muted", style="Red.TButton")

    def on_toggle_video_click(self):
        is_enabled = not self.video_enabled.get()
        self.video_enabled.set(is_enabled)
        
        if is_enabled:
            threading.Thread(target=self._start_camera_capture, daemon=True).start()
        else:
            threading.Thread(target=self._stop_camera_capture, daemon=True).start()
            if hasattr(self, 'video_btn') and self.video_btn.winfo_exists():
                self.video_btn.config(text="Video Off", style="Red.TButton")
            self._update_video_frame_visibility(self.username, show_video=False)
            self._send_tcp_message({'type': 'video_toggle', 'status': False})

    def _start_camera_capture(self):
        with self._camera_lock:
            if self.camera is not None: return
            try:
                self.camera = cv2.VideoCapture(0)
                if not self.camera.isOpened(): raise Exception("Camera failed to open")
                self.add_log_message("Video enabled")
                if hasattr(self, 'video_btn') and self.video_btn.winfo_exists():
                    self.root.after(0, lambda: self.video_btn.config(text="Video On", style="Control.TButton"))
                self._send_tcp_message({'type': 'video_toggle', 'status': True})
                self._update_video_frame_visibility(self.username, show_video=True)
            except Exception as e:
                self._handle_camera_failure(e)

    def _stop_camera_capture(self):
        with self._camera_lock:
            if self.camera is not None:
                try: self.camera.release()
                except Exception as e: print(f"Error releasing camera: {e}")
                self.camera = None
                self.add_log_message("Video disabled")

    def _handle_camera_failure(self, e):
        if not self.video_enabled.get(): return
        self.add_log_message(f"[ERROR] Camera failed: {e}. Disabling video.")
        self.video_enabled.set(False)
        with self._camera_lock: self.camera = None
        if hasattr(self, 'video_btn') and self.video_btn.winfo_exists():
            self.video_btn.config(text="Video Off", style="Red.TButton")
        self._update_video_frame_visibility(self.username, show_video=False)
        self._send_tcp_message({'type': 'video_toggle', 'status': False})

    def start_screen_share(self):
        if not self.screen_sharing_active.is_set():
            self.screen_sharing_active.set()
            self._send_tcp_message({'type': 'screen_start'})
            threading.Thread(target=self._run_screen_share_sender, daemon=True, name="Screen-Send").start()
            self.add_log_message("Started screen sharing...")
            if hasattr(self, 'share_btn') and self.share_btn.winfo_exists():
                self.share_btn.config(command=self.stop_screen_share, text="Stop Share", style="Red.TButton")
        else: self.add_log_message("You are already sharing.")

    def stop_screen_share(self):
        if self.screen_sharing_active.is_set():
            self.screen_sharing_active.clear()
            self._send_tcp_message({'type': 'screen_stop'})
            self.add_log_message("Stopped screen sharing.")
            if hasattr(self, 'share_btn') and self.share_btn.winfo_exists():
                self.share_btn.config(command=self.start_screen_share, text="Share", style="Control.TButton")
        else: self.add_log_message("You are not sharing.")
        
    # =================================================================================
    #   5. NETWORK SENDER LOOPS
    # =================================================================================

    def _send_tcp_message(self, message_dict):
        if not self.tcp_socket or not self.is_connected.is_set(): return
        try:
            data = pickle.dumps(message_dict)
            prefix = struct.pack("Q", len(data))
            with self.tcp_lock:
                self.tcp_socket.sendall(prefix + data)
        except (OSError, ConnectionError) as e:
            print(f"Failed to send TCP message: {e}")
        except Exception as e:
            print(f"Error packing TCP message: {e}")

    def _run_video_sender(self):
        try:
            while self.is_connected.is_set():
                frame_to_send = None
                frame_to_display = None
                
                with self._camera_lock:
                    if self.video_enabled.get() and self.camera is not None and self.camera.isOpened():
                        ret, frame = self.camera.read()
                        if not ret:
                            self.root.after(0, self._handle_camera_failure, "Camera read failed")
                            continue
                        frame = cv2.flip(frame, 1)
                        frame_to_send = frame
                        frame_to_display = frame.copy()

                if frame_to_send is not None:
                    frame_resized_send = cv2.resize(frame_to_send, (320, 240))
                    _, buffer = cv2.imencode('.jpg', frame_resized_send, [cv2.IMWRITE_JPEG_QUALITY, 40])
                    data = pickle.dumps({"type": "video", "from": self.username, "frame": buffer})
                    if self.udp_socket: self.udp_socket.sendto(data, self.server_udp_addr)
                    
                if frame_to_display is not None and self.my_video_label:
                    try:
                        label_w, label_h = self.my_video_label.winfo_width(), self.my_video_label.winfo_height()
                        # Dynamic resizing logic... (as in original)
                        if label_w < 10 or label_h < 10:
                            target_size = (120, 90) if self.is_presenting else (240, 180)
                        else:
                           h, w, _ = frame_to_display.shape 
                           aspect = w / h if h > 0 else 1.0
                           if label_w / aspect <= label_h: target_size = (label_w, int(label_w / aspect)) if aspect > 0 else (label_w, label_h)
                           else: target_size = (int(label_h * aspect), label_h) if aspect > 0 else (label_w, label_h)
                        
                        target_w, target_h = max(1, target_size[0]), max(1, target_size[1])
                        local_frame_resized = cv2.resize(frame_to_display, (target_w, target_h))
                        frame_rgb = cv2.cvtColor(local_frame_resized, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame_rgb)
                        imgtk = ImageTk.PhotoImage(image=img)
                        self.root.after(0, self._update_video_display, self.my_video_label, imgtk)
                    except Exception: pass
                
                if frame_to_send is None: threading.Event().wait(0.05) # Wait if video is disabled
        except Exception as e:
            print(f"Video sender thread crashed: {e}")
        finally:
            self._stop_camera_capture()
            print("Video sender thread stopped.")

    def _run_audio_sender(self):
        while self.is_connected.is_set():
            if self.audio_enabled.get() and self.audio_stream_in:
                try:
                    data = self.audio_stream_in.read(CHUNK, exception_on_overflow=False)
                    data_payload = pickle.dumps({"type": "audio", "from": self.username, "data": data})
                    if self.udp_socket: self.udp_socket.sendto(data_payload, self.server_udp_addr)
                except (IOError, OSError) as e:
                    self.add_log_message(f"[ERROR] Audio input failed: {e}")
                    self.audio_enabled.set(False)
                    if hasattr(self, 'audio_btn') and self.audio_btn.winfo_exists():
                        self.root.after(0, lambda: self.audio_btn.config(text="No Mic", style="Red.TButton", state='disabled'))
                except Exception: pass
            else:
                threading.Event().wait(0.05)

    def _run_screen_share_sender(self):
        # ... (Screen sharing loop logic from original) ...
        try:
            with mss.mss() as sct:
                monitor_to_capture = sct.monitors[1]
                while self.screen_sharing_active.is_set() and self.is_connected.is_set():
                    try:
                        img_shot = sct.grab(monitor_to_capture)
                        img_pil = Image.frombytes("RGB", img_shot.size, img_shot.rgb)
                        
                        base_width = 960
                        w_percent = (base_width / float(img_pil.size[0])) if img_pil.size[0] > 0 else 0
                        h_size = int((float(img_pil.size[1]) * float(w_percent)))
                        
                        target_w = max(1, base_width)
                        target_h = max(1, h_size)
                        
                        img_resized = img_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)

                        buffer = io.BytesIO()
                        img_resized.save(buffer, format="JPEG", quality=40) 
                        jpeg_bytes = buffer.getvalue()
                        
                        msg = {'type': 'screen', 'from': self.username, 'frame': jpeg_bytes}
                        
                        try:
                            data = pickle.dumps(msg)
                            if len(data) > 65000:
                                continue
                            if self.udp_socket:
                                self.udp_socket.sendto(data, self.server_udp_addr)
                        except Exception as e:
                            print(f"UDP send error: {e}")
                    except mss.ScreenShotError as ex:
                        self.add_log_message(f"Screen grab error: {ex}")
                        self.root.after(0, self.stop_screen_share) 
                        break 
                    except Exception as e:
                        self.add_log_message(f"Screen share error: {e}");
                        self.root.after(0, self.stop_screen_share) 
                        break
                    threading.Event().wait(0.066)
        except Exception as e:
            self.add_log_message(f"Could not initialize screen capture: {e}")
            if self.is_connected.is_set():
                self.root.after(0, self.stop_screen_share)

    # =================================================================================
    #   6. NETWORK RECEIVER LOOPS AND HANDLERS
    # =================================================================================
    
    def _run_tcp_receiver(self):
        try:
            while self.is_connected.is_set():
                if not self.tcp_socket: break
                prefix_data = self.tcp_socket.recv(8)
                if not prefix_data:
                    self.add_log_message("Server closed the connection.")
                    break 
                payload_size = struct.unpack("Q", prefix_data)[0]
                payload_data = b""
                while len(payload_data) < payload_size:
                    chunk_size = min(4096, payload_size - len(payload_data))
                    chunk = self.tcp_socket.recv(chunk_size)
                    if not chunk: raise ConnectionError("Server disconnected mid-payload")
                    payload_data += chunk
                message = pickle.loads(payload_data)
                self.root.after(0, self._handle_tcp_message, message)
        except (ConnectionResetError, ConnectionError, struct.error, EOFError, OSError) as e:
            if self.is_connected.is_set(): self.add_log_message(f"Connection lost to server: {e}")
        except Exception as e:
            if self.is_connected.is_set(): self.add_log_message(f"[ERROR] TCP Connection lost: {e}")
        finally:
            if self.is_connected.is_set():
                self.add_log_message("Disconnected. Cleaning up...")
                self.is_connected.clear() 
                self.root.after(0, self._trigger_shutdown)

    def _handle_tcp_message(self, msg):
        try:
            msg_type = msg.get('type')
            sender = msg.get('from', 'System')

            if msg_type == 'chat':
                self.add_chat_message(f"{sender}: {msg['content']}")
                self.toggle_side_panel('chat') # Show panel on new chat
                
            elif msg_type == 'user_list':
                current_users = set(msg['users'])
                existing_users = set(self.video_frames.keys())
                users_to_add = (current_users - existing_users) - {self.username}
                for user in users_to_add: self.add_user_feed(user, is_local=False)
                users_to_remove = (existing_users - current_users) - {self.username} 
                for user in users_to_remove: self.remove_user_feed(user)
                self._update_member_list(msg['users'])
                self.update_layout_grid()
                
            elif msg_type == 'system':
                sys_msg = msg['content']
                self.add_log_message(sys_msg)
                if sys_msg == 'Username already taken.':
                    if not hasattr(self, '_rejection_shown'):
                        self._rejection_shown = True
                        messagebox.showerror("Connection Failed", "That username is already in use.")
                        self.on_closing(force=True) 
                        
            elif msg_type == 'screen_start':
                self.is_presenting = True
                self.screen_presenter_name.set(f"{sender} is presenting")
                self.avatar_grid_frame.pack_forget()
                self.screen_share_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                self.presenter_video_sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
                if sender == self.username:
                    self.share_btn.config(command=self.stop_screen_share, text="Stop Share", style="Red.TButton")
                else:
                    self.share_btn.config(state='disabled')
                self.update_layout_grid()
                
            elif msg_type == 'screen_stop':
                presenter_name = self.screen_presenter_name.get().split(" ")[0]
                if sender == presenter_name or not presenter_name or presenter_name == "No": 
                    self.is_presenting = False
                    self.screen_sharing_active.clear() 
                    self.screen_presenter_name.set("No one is presenting")
                    if self.screen_share_label.winfo_ismapped(): self.screen_share_label.pack_forget()
                    if self.presenter_video_sidebar.winfo_ismapped(): self.presenter_video_sidebar.pack_forget()
                    if not self.avatar_grid_frame.winfo_ismapped(): self.avatar_grid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
                    if hasattr(self, 'share_btn') and self.share_btn.winfo_exists():
                        self.share_btn.config(command=self.start_screen_share, text="Share", style="Control.TButton", state='normal')
                    self.update_layout_grid()
                    
            elif msg_type == 'video_toggle':
                if sender in self.video_frames:
                    status = msg['status']
                    self.video_frames[sender]['remote_video_status'] = status
                    self._update_video_frame_visibility(sender, show_video=status)
                    self.add_log_message(f"{sender} turned video {'on' if status else 'off'}")

            elif msg_type == 'file_init_request':
                self._handle_file_offer(msg)
                self.toggle_side_panel('files')
            elif msg_type == 'file_accept':
                self._handle_file_acceptance(msg)
            elif msg_type == 'file_reject':
                self._handle_file_rejection(msg)
        
        except KeyError as e:
            print(f"CRITICAL: KeyError handling TCP message: {e}. Message was: {msg}")
        except Exception as e:
            print(f"Error handling TCP message: {e}")

    def _run_udp_receiver(self):
        while self.is_connected.is_set():
            try:
                if not self.udp_socket: break
                packet, _ = self.udp_socket.recvfrom(65536)
                payload = pickle.loads(packet)
                sender = payload.get("from", "Unknown")
                if sender == self.username: continue
                msg_type = payload.get("type")
                
                if msg_type == "audio":
                    if self.audio_stream_out and sender != self.username:
                        try: self.audio_stream_out.write(payload["data"])
                        except Exception: pass
                        
                elif msg_type == "video":
                    self._handle_remote_video_data(sender, payload)
                        
                elif msg_type == "screen":
                    self._handle_screen_data(payload)
                    
            except (pickle.UnpicklingError, KeyError): pass
            except OSError: break
            except Exception as e:
                print(f"UDP Receive Error: {e}")
                pass

    def _handle_remote_video_data(self, sender, payload):
        if sender not in self.video_frames:
            self.root.after(0, self.add_user_feed, sender, False)
            return
            
        if self.video_frames[sender].get('remote_video_status', False):
            label_widget = self.video_frames[sender].get('label')
            if label_widget:
                frame_data = payload["frame"]
                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), 1)

                try:
                   label_w, label_h = label_widget.winfo_width(), label_widget.winfo_height()
                   # Dynamic resizing logic... (as in original)
                   if label_w < 10 or label_h < 10:
                       target_size = (120, 90) if self.is_presenting else (240, 180)
                   else:
                       h, w, _ = frame.shape
                       aspect = w / h if h > 0 else 1.0
                       if label_w / aspect <= label_h: target_size = (label_w, int(label_w / aspect)) if aspect > 0 else (label_w, label_h)
                       else: target_size = (int(label_h * aspect), label_h) if aspect > 0 else (label_w, label_h)
                   
                   target_w, target_h = max(1, target_size[0]), max(1, target_size[1])
                   frame = cv2.resize(frame, (target_w, target_h))
                   
                except tk.TclError:
                   target_size = (120, 90) if self.is_presenting else (240, 180)
                   frame = cv2.resize(frame, target_size)
                   
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                self.root.after(0, self._update_video_display, label_widget, imgtk)

    def _handle_screen_data(self, message):
        try:
            if not self.screen_share_label.winfo_exists(): return
            img_bytes = message['frame']
            img_stream = io.BytesIO(img_bytes)
            img = Image.open(img_stream)
            w, h = self.screen_share_label.winfo_width(), self.screen_share_label.winfo_height()
            if w < 10 or h < 10: w, h = 800, 600
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            self.screen_share_label.imgtk = imgtk
            self.screen_share_label.config(image=imgtk)
        except Exception as e: 
            print(f"Screen data handle error: {e}")
            pass

    # =================================================================================
    #   7. CHAT AND MEMBER LIST MANAGEMENT
    # =================================================================================

    def _send_chat_message_event(self, event=None):
        message = self.chat_input.get()
        if message and self.is_connected.is_set():
            self.add_chat_message(f"You: {message}")
            self._send_tcp_message({'type': 'chat', 'content': message})
            self.chat_input.delete(0, tk.END)

    def add_chat_message(self, message):
        def _add():
            if hasattr(self, 'chat_area') and self.chat_area.winfo_exists():
                try:
                    self.chat_area.config(state='normal')
                    if message.startswith("You:"): self.chat_area.insert(tk.END, message + '\n', 'local_user')
                    elif message.startswith("---"): self.chat_area.insert(tk.END, message + '\n', 'system')
                    else: self.chat_area.insert(tk.END, message + '\n', 'remote_user')
                    self.chat_area.config(state='disabled')
                    self.chat_area.see(tk.END)
                except tk.TclError: pass
        if self.root.winfo_exists():
            if 'local_user' not in self.chat_area.tag_names():
                self.chat_area.tag_config('local_user', foreground=BTN_SUCCESS, font=("Consolas", 10, "bold"))
                self.chat_area.tag_config('remote_user', foreground=ACCENT_COLOR, font=("Consolas", 10))
                self.chat_area.tag_config('system', foreground=FG_DARKER, font=("Consolas", 10, "italic"))
            self.root.after(0, _add)

    def add_log_message(self, message):
         self.add_chat_message(f"--- {message} ---")

    def _update_member_list(self, users):
        if not hasattr(self, 'member_listbox') or not self.member_listbox.winfo_exists(): return
        self.member_listbox.delete(0, tk.END)
        for i, user in enumerate(users):
            display_name = f" {i+1}. {user}"
            if user == self.username: display_name += " (You)"
            self.member_listbox.insert(tk.END, display_name)
            if user == self.username:
                self.member_listbox.itemconfig(tk.END, {'fg': BTN_SUCCESS, 'bg': BG_COLOR})
            else:
                self.member_listbox.itemconfig(tk.END, {'fg': FG_COLOR, 'bg': LIST_BG if i%2==0 else FRAME_BG})

    # =================================================================================
    #   8. FILE TRANSFER LOGIC
    # =================================================================================

    def _select_file_to_send(self):
        if not self.is_connected.is_set(): return
        
        filepath = filedialog.askopenfilename(title="Select file to send")
        if not filepath: return

        other_users = [u for u in self.video_frames.keys() if u != self.username]
        
        if not other_users:
            self.add_log_message("No one else is in the call to send a file to.")
            return
        
        target_users = self._ask_for_target_user(other_users)
        if not target_users:
            self.add_log_message("File send cancelled.")
            return
        
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        
        self._temp_filepath_store[filename] = filepath
        
        for target_user in target_users:
            if not target_user: continue 
            
            transfer_id = f"{filename}_{self.username}_{target_user}"
            if transfer_id in self.active_file_transfers:
                self.add_log_message(f"Already sending {filename} to {target_user}")
                continue
                
            self.active_file_transfers.add(transfer_id)
            
            init_msg = {
                'type': 'file_init_request', 
                'filename': filename, 
                'size': filesize,
                'to_user': target_user
            }
            self._send_tcp_message(init_msg)
            self.add_log_message(f"Offering file: {filename} to {target_user}. Waiting...")
            self._add_file_log_entry(time.time(), self.username, filename, "Offered", receiver=target_user)

    def _ask_for_target_user(self, user_list):
        # ... (GUI code for selecting target user from original) ...
        dialog = tk.Toplevel(self.root)
        dialog.title("Select User(s)")
        dialog.configure(bg=BG_COLOR)
        dialog.resizable(False, False)
        
        ttk.Label(dialog, text="Who do you want to send this file to?", font=("Arial", 12)).pack(padx=20, pady=10)
        
        listbox = Listbox(dialog, bg=LIST_BG, fg=FG_COLOR, selectbackground=ACCENT_COLOR, 
                          font=("Arial", 10), relief=tk.FLAT, borderwidth=0, highlightthickness=0,
                          selectmode=tk.MULTIPLE, exportselection=False)
        
        for user in user_list:
            listbox.insert(tk.END, user)
        listbox.pack(padx=20, pady=10, fill=tk.X)
        
        result = tk.StringVar(value="")
        
        def on_select_all():
            listbox.select_set(0, tk.END)

        def on_ok():
            try:
                selected_indices = listbox.curselection()
                selected_users = [listbox.get(i) for i in selected_indices]
                
                if selected_users:
                    result.set(','.join(selected_users))
                    dialog.destroy()
                else:
                    messagebox.showwarning("No Selection", "Please select at least one user.", parent=dialog)
            except tk.TclError:
                pass
                
        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(padx=20, pady=10)
        
        ttk.Button(btn_frame, text="Select All", command=on_select_all, style="Control.TButton").pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Send", command=on_ok, style="Blue.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, style="Control.TButton").pack(side=tk.LEFT, padx=5)
        
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)
        
        return result.get().split(',') if result.get() else []

    def _handle_file_offer(self, msg):
        filename, filesize, sender = msg['filename'], msg['size'], msg['from_user']
        transfer_id = f"{filename}_{sender}_{self.username}"
        self._add_file_log_entry(time.time(), sender, filename, "Offered to you") 

        if messagebox.askyesno("File Transfer",
                               f"{sender} wants to send you:\n\n{filename}\n({filesize // 1024} KB)\n\nAccept?"):
            save_path = filedialog.asksaveasfilename(title=f"Save {filename}", initialfile=filename)
            if not save_path:
                self.add_log_message(f"Rejected file: {filename}")
                self._update_file_log_status(filename, sender, "Rejected by you")
                self._send_tcp_message({'type': 'file_reject', 'from_user': sender, 'filename': filename})
                return

            self.active_file_transfers.add(transfer_id)
            threading.Thread(target=self._run_p2p_file_receiver, 
                             args=(filename, sender, save_path, transfer_id), 
                             daemon=True,
                             name="P2P-Recv").start()
        else:
            self.add_log_message(f"Rejected file: {filename}")
            self._update_file_log_status(filename, sender, "Rejected by you")
            self._send_tcp_message({'type': 'file_reject', 'from_user': sender, 'filename': filename})

    def _run_p2p_file_receiver(self, filename, sender, save_path, transfer_id):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(('', 0))
            port = server_socket.getsockname()[1]
            server_socket.listen(1)
            
            accept_msg = {
                'type': 'file_accept',
                'filename': filename,
                'from_user': sender,
                'port': port
            }
            self._send_tcp_message(accept_msg)
            self.root.after(0, self._update_file_log_status, filename, sender, "P2P-Receiving")
            
            self.add_log_message(f"Waiting for {sender} to connect for {filename}...")
            conn, addr = server_socket.accept()
            self.add_log_message(f"{sender} connected! Receiving {filename}...")

            with open(save_path, 'wb') as f:
                while True:
                    chunk = conn.recv(4096)
                    if not chunk: break
                    f.write(chunk)
            
            self.root.after(0, self.add_log_message, f"File {filename} received successfully!")
            self.root.after(0, self._update_file_log_status, filename, sender, "Received (P2P)")
            
        except Exception as e:
            self.root.after(0, self.add_log_message, f"[ERROR] P2P Receive failed for {filename}: {e}")
            self.root.after(0, self._update_file_log_status, filename, sender, "P2P-Fail")
        finally:
            if 'conn' in locals(): conn.close()
            if 'server_socket' in locals(): server_socket.close()
            self.active_file_transfers.discard(transfer_id)

    def _handle_file_acceptance(self, msg):
        filename = msg['filename']
        receiver = msg.get('from')
        if not receiver: return
        
        ip, port = msg['ip'], msg['port']
        filepath = self._temp_filepath_store.get(filename)
        
        if not filepath:
            self.add_log_message(f"[ERROR] Could not find filepath for {filename}")
            return
            
        self.add_log_message(f"{receiver} accepted {filename}. Starting P2P send to {ip}:{port}")
        self._update_file_log_status(filename, self.username, "P2P-Sending", receiver=receiver)
        
        threading.Thread(target=self._run_p2p_file_sender, 
                         args=(filepath, filename, ip, port, receiver), 
                         daemon=True,
                         name="P2P-Send").start()

    def _run_p2p_file_sender(self, filepath, filename, ip, port, receiver):
        transfer_id = f"{filename}_{self.username}_{receiver}"
        client_socket = None
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, port))
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    client_socket.sendall(chunk)
            
            self.root.after(0, lambda: self.add_log_message(f"File {filename} sent successfully to {receiver}."))
            self.root.after(0, lambda: self._update_file_log_status(filename, self.username, "Sent (P2P)", receiver=receiver))
            
        except Exception as e:
            self.root.after(0, lambda: self.add_log_message(f"[ERROR] P2P Send failed for {filename}: {e}"))
            self.root.after(0, lambda: self._update_file_log_status(filename, self.username, "P2P-Fail", receiver=receiver))
        finally:
            if client_socket: client_socket.close()
            self.active_file_transfers.discard(transfer_id)

    def _handle_file_rejection(self, msg):
        filename = msg['filename']
        receiver = msg.get('from') 
        if not receiver: return
             
        self.add_log_message(f"{receiver} rejected your file: {filename}")
        self._update_file_log_status(filename, self.username, "Rejected", receiver=receiver)
        
        transfer_id = f"{filename}_{self.username}_{receiver}"
        self.active_file_transfers.discard(transfer_id)

    def _add_file_log_entry(self, timestamp, sender, filename, status, receiver=None):
        log_entry = {'timestamp': timestamp, 'sender': sender, 'filename': filename, 'status': status, 'receiver': receiver}
        self._file_log_entries.append(log_entry)
        self._update_file_log_display()

    def _update_file_log_status(self, filename, sender, new_status, receiver=None):
         found = False
         for entry in reversed(self._file_log_entries):
             if entry['filename'] == filename and entry['sender'] == sender and \
                (receiver is None or entry['receiver'] == receiver or entry['receiver'] is None): 
                  entry['status'] = new_status
                  if receiver and entry['receiver'] is None: entry['receiver'] = receiver
                  found = True
                  break
         if found: self._update_file_log_display()

    def _update_file_log_display(self):
        def _update():
            if hasattr(self, 'file_log_area') and self.file_log_area.winfo_exists():
                try:
                    self.file_log_area.config(state='normal')
                    self.file_log_area.delete('1.0', tk.END)
                    for entry in reversed(self._file_log_entries):
                        ts = time.strftime("%H:%M:%S", time.localtime(entry['timestamp']))
                        log_line = f"[{ts}] "
                        status = entry['status']
                        if status == 'P2P-Receiving':
                            log_line += f"Receiving '{entry['filename']}' from {entry['sender']}... (Direct)"
                        elif status == 'P2P-Sending':
                            log_line += f"Sending '{entry['filename']}' to {entry['receiver']}... (Direct)"
                        elif entry['sender'] == self.username:
                            log_line += f"You offered '{entry['filename']}' ({status})"
                            if entry['receiver']: log_line += f" to {entry['receiver']}"
                        else:
                            log_line += f"{entry['sender']} offered '{entry['filename']}' ({status})"
                        self.file_log_area.insert(tk.END, log_line + '\n')
                    self.file_log_area.config(state='disabled')
                    self.file_log_area.see(tk.END)
                except tk.TclError: pass
        if self.root.winfo_exists(): self.root.after(0, _update)

if __name__ == "__main__":
    root = tk.Tk()
    try:
        s = ttk.Style()
        s.configure('TDialog.TFrame', background=BG_COLOR)
        s.configure('TDialog.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=("Arial", 10))
        s.configure('TDialog.TEntry', fieldbackground=LIST_BG, foreground=FG_COLOR, borderwidth=0, relief=tk.FLAT, insertbackground=FG_COLOR, padding=8)
        s.configure('TDialog.TButton', font=("Arial", 10, "bold"), padding=8, relief=tk.FLAT, borderwidth=0, background=ACCENT_COLOR, foreground="white")
        s.map('TDialog.TButton', background=[('active', ACCENT_DARK)])
        root.option_add('*Dialog.msg.font', ('Arial', 10))
        root.option_add('*Dialog.Entry.background', LIST_BG)
        root.option_add('*Dialog.Entry.foreground', FG_COLOR)
        root.option_add('*Dialog.Entry.borderWidth', 0)
        root.option_add('*Dialog.Entry.relief', 'flat')
        root.option_add('*Dialog.OK.background', ACCENT_COLOR)
        root.option_add('*Dialog.OK.foreground', 'white')
        root.option_add('*Dialog.OK.relief', 'flat')
        root.option_add('*Dialog.Cancel.background', FRAME_BG)
        root.option_add('*Dialog.Cancel.foreground', FG_COLOR)
        root.option_add('*Dialog.Cancel.relief', 'flat')
    except Exception: pass

    app = ClientGUI(root)
    if app.username and app.root.winfo_exists():
        root.mainloop()