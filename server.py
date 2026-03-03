import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, Frame, Listbox
from tkinter import ttk
import pickle
import struct
import logging
import os

# --- Configuration ---
LISTEN_HOST = '0.0.0.0'
CONTROL_PORT = 3478  # TCP Port for control/chat/metadata
MEDIA_PORT = 6734    # UDP Port for media/screen
# ---------------------

# --- Style Configuration (Improved Combo) ---
BG_COLOR = "#0D1117"     # Deep Black
FRAME_BG = "#161B22"     # Container/Panel Background
LIST_BG = "#161B22"      # List Background
LOG_BG = "#0D1117"       # Log Area Background
FG_COLOR = "#C9D1D9"     # Foreground Text (Light Gray)
ACCENT_COLOR = "#58A6FF" # Primary Accent (Vibrant Blue)
ACCENT_DARK = "#1F6ED8"  # Accent Dark (Active Blue)
BTN_SUCCESS = "#3FB950"  # Success/Mic On (Green)
BTN_DANGER = "#F85149"   # Danger/Video Off (Red)
# --------------------------------------------

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(threadName)s] %(message)s')

class ServerControlPanel:
    """Manages the server logic (TCP/UDP) and provides a monitoring GUI."""
    
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("LANMeet (Control Panel)")
        self.root.geometry("700x500")
        self.root.configure(bg=BG_COLOR)

        # --- State Variables ---
        self.tcp_clients_map = {}  # {socket: (username, udp_addr, tcp_ip)}
        self.username_to_socket = {} # {username: socket}
        self.active_udp_addresses = set()
        self.client_state_lock = threading.Lock()
        
        # Sockets
        self.tcp_listener = None
        self.udp_relay = None
        
        # --- Initialization ---
        self._setup_gui_elements()
        
        self._utility_log_message("Server starting...")
        self.server_ip_address = self._utility_get_lan_ip()
        self._setup_tcp_listener()
        self._setup_udp_listener()
        
        # Set protocol handler for window closing
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_closing)

    # =================================================================================
    #   1. GUI SETUP AND UTILITIES
    # =================================================================================

    def _setup_gui_elements(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".", background=BG_COLOR, foreground=FG_COLOR, fieldbackground=FRAME_BG, bordercolor=FRAME_BG, lightcolor=FRAME_BG, darkcolor=FRAME_BG)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Arial", 10))
        style.configure("Vertical.TScrollbar", background=ACCENT_DARK, troughcolor=FRAME_BG, arrowcolor=FG_COLOR, bordercolor=FRAME_BG)
        style.map("Vertical.TScrollbar", background=[('active', ACCENT_COLOR)])
        
        # Custom button style for the Stop button
        style.configure("Danger.TButton", background=BTN_DANGER, foreground="white", font=("Arial", 10, "bold"), padding=8)
        style.map("Danger.TButton", background=[('active', ACCENT_DARK)])
        
        main_frame = Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Log Panel
        log_frame = Frame(main_frame, bg=BG_COLOR)
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(log_frame, text="Server Activity Log", font=("Arial", 14, "bold"), foreground=ACCENT_COLOR).pack(pady=(0, 10), anchor='w')
        self.log_scroll_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=15, 
                                                  bg=LOG_BG, fg=FG_COLOR, insertbackground=FG_COLOR,
                                                  font=("Consolas", 10), relief=tk.FLAT, borderwidth=0,
                                                  highlightthickness=1, highlightbackground=FRAME_BG)
        self.log_scroll_area.pack(fill=tk.BOTH, expand=True)
        
        # Client Panel
        client_frame = Frame(main_frame, bg=BG_COLOR)
        client_frame.grid(row=0, column=1, sticky="nsew")
        ttk.Label(client_frame, text="Connected Clients", font=("Arial", 14, "bold"), foreground=ACCENT_COLOR).pack(pady=(0, 10), anchor='w')
        self.client_listbox = Listbox(client_frame, height=10, 
                                      bg=LIST_BG, fg=FG_COLOR, 
                                      selectbackground=ACCENT_COLOR, 
                                      font=("Arial", 10), relief=tk.FLAT, borderwidth=0,
                                      highlightthickness=0)
        self.client_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Info Panel
        info_frame = Frame(client_frame, bg=BG_COLOR)
        info_frame.pack(fill=tk.X, pady=(10,0))
        
        server_ip = self._utility_get_lan_ip()
        
        ttk.Label(info_frame, text="Server Status: Online", font=("Arial", 9, "bold"), foreground=BTN_SUCCESS).pack(anchor='w')
        ttk.Label(info_frame, text=f"IP: {server_ip}", font=("Arial", 9, "bold"), foreground="#FFD700").pack(anchor='w')
        ttk.Label(info_frame, text=f"TCP Port: {CONTROL_PORT}", font=("Arial", 9), foreground="#AAAAAA").pack(anchor='w')
        ttk.Label(info_frame, text=f"UDP Port: {MEDIA_PORT}", font=("Arial", 9), foreground="#AAAAAA").pack(anchor='w')
        
        # --- NEW: Stop Server Button ---
        self.stop_button = ttk.Button(client_frame, text="Stop Server", style="Danger.TButton", command=self._on_window_closing)
        self.stop_button.pack(fill=tk.X, pady=(10, 0))
        
        self._utility_log_message(f"Share this IP with clients: {server_ip}")

    def _utility_get_lan_ip(self):
        """Get the actual LAN IP address of the server."""
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.connect(("8.8.8.8", 80)) # Connect to an external address
            ip = temp_socket.getsockname()[0]
            temp_socket.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _utility_log_message(self, message):
        logging.info(message)
        def _log():
            if not self.root.winfo_exists(): return
            self.log_scroll_area.config(state='normal')
            self.log_scroll_area.insert(tk.END, f"{message}\n")
            self.log_scroll_area.config(state='disabled')
            self.log_scroll_area.see(tk.END)
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(0, _log)

    def _manage_client_display(self):
        def _update():
            if not self.root.winfo_exists(): return
            self.client_listbox.delete(0, tk.END)
            with self.client_state_lock:
                clients_data = list(self.tcp_clients_map.values())
            
            for i, (username, udp_addr, tcp_ip) in enumerate(clients_data):
                self.client_listbox.insert(tk.END, f" {username} @ {tcp_ip}")
                self.client_listbox.itemconfig(tk.END, bg=LIST_BG if i % 2 == 0 else FRAME_BG)
        
        if self.root.winfo_exists():
            self.root.after(0, _update)

    # =================================================================================
    #   2. NETWORK SETUP AND RUNNING LOOPS
    # =================================================================================

    def _setup_tcp_listener(self):
        try:
            self.tcp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_listener.bind((LISTEN_HOST, CONTROL_PORT))
            self.tcp_listener.listen(5)
            self._utility_log_message(f"TCP Listener active on {LISTEN_HOST}:{CONTROL_PORT}")
            
            acceptor_thread = threading.Thread(target=self._run_tcp_acceptor, name="TCP-Accept", daemon=True)
            acceptor_thread.start()
        except Exception as e:
            self._utility_log_message(f"[FATAL ERROR] TCP Setup: {e}")

    def _run_tcp_acceptor(self):
        client_counter = 1
        while True:
            try:
                client_socket, (client_ip, client_tcp_port) = self.tcp_listener.accept()
                self._utility_log_message(f"New connection from {client_ip}:{client_tcp_port}")
                
                handler_thread = threading.Thread(target=self._run_client_handler, 
                                                 args=(client_socket, client_ip), 
                                                 name=f"Client-{client_counter}",
                                                 daemon=True)
                handler_thread.start()
                client_counter += 1
            except OSError:
                self._utility_log_message("TCP Listener shutting down.")
                break
            except Exception as e:
                self._utility_log_message(f"[ERROR] Accepting connection: {e}")

    def _setup_udp_listener(self):
        try:
            self.udp_relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_relay.bind((LISTEN_HOST, MEDIA_PORT))
            self._utility_log_message(f"UDP Relay active on {LISTEN_HOST}:{MEDIA_PORT}")
            relay_thread = threading.Thread(target=self._run_udp_relay, name="UDP-Relay", daemon=True)
            relay_thread.start()
        except Exception as e:
            self._utility_log_message(f"[FATAL ERROR] UDP Setup: {e}")

    def _run_udp_relay(self):
        while True:
            try:
                # Max UDP payload size is ~64KB
                data, sender_addr = self.udp_relay.recvfrom(65536) 
                
                with self.client_state_lock:
                    if sender_addr not in self.active_udp_addresses:
                        # Drop packet from unknown/unregistered sender
                        continue 
                        
                    targets = [
                        udp_addr for (username, udp_addr, ip) in self.tcp_clients_map.values() 
                        if udp_addr is not None and udp_addr != sender_addr
                    ]
                
                # Relay data to all other connected clients
                for target_addr in targets:
                    try:
                        self.udp_relay.sendto(data, target_addr)
                    except Exception: pass
            except OSError:
                self._utility_log_message("UDP Relay shutting down.")
                break
            except Exception as e:
                self._utility_log_message(f"[ERROR] UDP Relay: {e}. Packet dropped.")

    # =================================================================================
    #   3. CLIENT MANAGEMENT AND HANDLERS
    # =================================================================================

    def _run_client_handler(self, client_socket, client_ip):
        client_username = None
        client_udp_addr = None
        
        try:
            # 1. Receive and process JOIN metadata
            metadata = client_socket.recv(1024).decode('utf-8')
            parts = metadata.split(':')
            if not (parts[0] == 'JOIN' and len(parts) == 3):
                raise ValueError(f"Invalid JOIN request from {client_ip}")

            client_username = parts[1]
            client_udp_port = int(parts[2])
            
            with self.client_state_lock:
                if client_username in self.username_to_socket:
                    self._utility_log_message(f"Username '{client_username}' already taken. Disconnecting {client_ip}.")
                    rejection_msg = {'type': 'system', 'content': 'Username already taken.'}
                    self._send_tcp_data(client_socket, rejection_msg, acquire_lock=False)
                    client_socket.close()
                    return
            
            client_udp_addr = (client_ip, client_udp_port)
            
            # 2. Register client
            with self.client_state_lock:
                self.tcp_clients_map[client_socket] = (client_username, client_udp_addr, client_ip)
                self.username_to_socket[client_username] = client_socket
                self.active_udp_addresses.add(client_udp_addr) 
            
            self._utility_log_message(f"Client '{client_username}' joined from {client_ip}:{client_udp_port}")
            self._broadcast_user_list() 
            self._manage_client_display()

            # 3. Main TCP Message Loop
            while True:
                prefix_data = client_socket.recv(8)
                if not prefix_data: break # Client closed connection
                
                payload_size = struct.unpack("Q", prefix_data)[0]
                payload_data = b""
                
                while len(payload_data) < payload_size:
                    chunk_size = min(4096, payload_size - len(payload_data))
                    chunk = client_socket.recv(chunk_size)
                    if not chunk: raise ConnectionError("Client disconnected mid-payload")
                    payload_data += chunk
                
                message = pickle.loads(payload_data)
                message['from'] = client_username # Enforce sender ID
                
                self._process_tcp_message(message, client_socket, client_username)

        except (ConnectionResetError, ConnectionError, EOFError, struct.error, ValueError, OSError) as e:
            self._utility_log_message(f"Client {client_username or client_ip} disconnected: {e}")
        except Exception as e:
            self._utility_log_message(f"[ERROR] Client {client_username or client_ip}: {e}")
        
        finally:
            self._manage_remove_client(client_socket)

    def _process_tcp_message(self, message_dict, sender_socket, sender_username):
        msg_type = message_dict.get('type')
        
        if msg_type in ['file_init_request', 'file_reject']:
            # P2P file initiation/rejection is relayed to the target user
            target_name = message_dict.get('to_user') or message_dict.get('from_user')
            message_dict['from_user'] = sender_username # Ensure the initial offer is from the actual sender
            self._relay_message(message_dict, target_name, f"file {msg_type} to {target_name}")
            
        elif msg_type == 'file_accept':
            # P2P file acceptance is relayed back to the original file offerer
            target_name = message_dict.get('from_user')
            
            with self.client_state_lock:
                (_, _, sender_ip) = self.tcp_clients_map.get(sender_socket, (None, None, None))
            
            if sender_ip:
                # Inject the acceptor's IP for the P2P connection
                message_dict['ip'] = sender_ip
                message_dict['from'] = sender_username
                self._relay_message(message_dict, target_name, f"file accept to {target_name}")
            else:
                self._utility_log_message(f"[ERROR] Could not find IP for {sender_username} (acceptor)")

        elif msg_type in ['chat', 'video_toggle', 'screen_start', 'screen_stop']:
            # General broadcast messages
            self._broadcast_message(message_dict, sender_socket, sender_username)
            if msg_type == 'chat':
                 self._utility_log_message(f"Chat from {sender_username}: {message_dict['content'][:50]}...")
        
        else:
            self._utility_log_message(f"[WARN] Unknown or media-type message '{msg_type}' received on TCP. Dropping.")

    def _manage_remove_client(self, client_socket):
        client_username = None
        udp_addr_to_remove = None
        user_list_changed = False

        with self.client_state_lock:
            if client_socket in self.tcp_clients_map:
                client_username, udp_addr_to_remove, _ = self.tcp_clients_map.pop(client_socket)
                user_list_changed = True
                
                if udp_addr_to_remove:
                    self.active_udp_addresses.discard(udp_addr_to_remove)
                    
                if client_username and client_username in self.username_to_socket and self.username_to_socket[client_username] == client_socket:
                    del self.username_to_socket[client_username]
        
        # Clean up socket resources
        # Use close() instead of shutdown() to reliably break client handler loops
        try: client_socket.close()
        except Exception: pass

        if user_list_changed and client_username:
            self._utility_log_message(f"'{client_username}' has left. Cleaning up.")
            # Notify clients of screen share stop (if this client was presenting)
            self._broadcast_message({'type': 'screen_stop', 'from': client_username}, None, "System")
            self._broadcast_user_list()
            self._manage_client_display()
        elif user_list_changed:
            self._utility_log_message("Unknown client disconnected. Cleaned up socket.")

    # =================================================================================
    #   4. COMMUNICATION METHODS
    # =================================================================================

    def _send_tcp_data(self, target_socket, message_dict, acquire_lock=True):
        try:
            data = pickle.dumps(message_dict)
            prefix = struct.pack("Q", len(data))
            
            if acquire_lock:
                with threading.Lock(): 
                    target_socket.sendall(prefix + data)
            else:
                target_socket.sendall(prefix + data)
                
        except Exception as e:
            self._utility_log_message(f"[WARN] Failed to send to client: {e}. Removing client.")
            self._manage_remove_client(target_socket)

    def _relay_message(self, message_dict, target_username, log_info=""):
        if not target_username:
            self._utility_log_message("[WARN] Tried to relay message to 'None' user.")
            return
            
        with self.client_state_lock:
            target_socket = self.username_to_socket.get(target_username)
            
        if target_socket:
            self._utility_log_message(f"Relaying {message_dict['type']} {log_info}")
            self._send_tcp_data(target_socket, message_dict)
        else:
            self._utility_log_message(f"[WARN] Could not relay message to unknown user {target_username}")

    def _broadcast_user_list(self):
        with self.client_state_lock:
            user_list = [val[0] for val in self.tcp_clients_map.values()]
        
        self._utility_log_message(f"Broadcasting updated user list: {user_list}")
        self._broadcast_message({'type': 'user_list', 'users': sorted(user_list)}, None, "System")

    def _broadcast_message(self, message_dict, sender_socket, sender_username):
        if 'from' not in message_dict:
             message_dict['from'] = sender_username or "Unknown"
        
        with self.client_state_lock:
            clients_snapshot = list(self.tcp_clients_map.keys())
            
        for client_socket in clients_snapshot:
            if client_socket != sender_socket:
                self._send_tcp_data(client_socket, message_dict)

    # =================================================================================
    #   5. SHUTDOWN
    # =================================================================================

    def _on_window_closing(self):
        self._utility_log_message("Server is shutting down...")
        
        # Closing the listening sockets will stop the acceptor and relay threads
        if hasattr(self, 'tcp_listener') and self.tcp_listener: 
             try: self.tcp_listener.close()
             except Exception: pass
        if hasattr(self, 'udp_relay') and self.udp_relay: 
             try: self.udp_relay.close()
             except Exception: pass
            
        # Disconnect all active clients
        # Use a list snapshot to iterate while the map is being modified by _manage_remove_client
        with self.client_state_lock:
            clients_snapshot = list(self.tcp_clients_map.keys())
            
        self._utility_log_message(f"Closing {len(clients_snapshot)} client connections...")
        
        # Note: Closing the client sockets here relies on _manage_remove_client being called
        # from the client handler thread, but since we are shutting down, we can iterate and close them.
        for client_socket in clients_snapshot:
            self._manage_remove_client(client_socket)
            
        self._utility_log_message("Cleanup complete. Exiting.")
        if self.root.winfo_exists(): self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    
    # Custom style configuration for dialogs (inherited from the previous context)
    try:
        s = ttk.Style()
        s.configure('TDialog.TFrame', background=BG_COLOR)
        s.configure('TDialog.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=("Arial", 10))
        s.configure('TDialog.TEntry', fieldbackground=LIST_BG, foreground=FG_COLOR, borderwidth=0, relief=tk.FLAT, insertbackground=FG_COLOR, padding=8)
        s.configure('TDialog.TButton', font=("Arial", 10, "bold"), padding=8, relief=tk.FLAT, borderwidth=0, background=ACCENT_COLOR, foreground="white")
        s.map('TDialog.TButton', background=[('active', ACCENT_DARK)])
    except Exception:
        pass
        
    app = ServerControlPanel(root)
    root.mainloop()