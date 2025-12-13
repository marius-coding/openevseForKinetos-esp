#!/usr/bin/env python3
"""
OpenEVSE Firmware Uploader - GUI tool for uploading firmware to OpenEVSE wallboxes.
"""

import sys
import platform
import subprocess

# Check if tkinter is available
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    print("=" * 70)
    print("ERROR: tkinter is not installed")
    print("=" * 70)
    print("\ntkinter is required to run this GUI application.\n")
    
    # Detect OS and provide instructions
    system = platform.system()
    
    if system == "Linux":
        # Try to detect Linux distribution
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read().lower()
                
            if 'ubuntu' in os_info or 'debian' in os_info or 'mint' in os_info:
                print("Installation command for Ubuntu/Debian/Mint:")
                print("  sudo apt update")
                print("  sudo apt install python3-tk")
            elif 'fedora' in os_info or 'rhel' in os_info or 'centos' in os_info:
                print("Installation command for Fedora/RHEL/CentOS:")
                print("  sudo dnf install python3-tkinter")
            elif 'arch' in os_info or 'manjaro' in os_info:
                print("Installation command for Arch/Manjaro:")
                print("  sudo pacman -S tk")
            elif 'opensuse' in os_info:
                print("Installation command for openSUSE:")
                print("  sudo zypper install python3-tk")
            else:
                print("Installation command for most Linux distributions:")
                print("  Debian/Ubuntu: sudo apt install python3-tk")
                print("  Fedora/RHEL:   sudo dnf install python3-tkinter")
                print("  Arch:          sudo pacman -S tk")
        except Exception:
            print("Installation command for most Linux distributions:")
            print("  Debian/Ubuntu: sudo apt install python3-tk")
            print("  Fedora/RHEL:   sudo dnf install python3-tkinter")
            print("  Arch:          sudo pacman -S tk")
    
    elif system == "Darwin":  # macOS
        print("Installation instructions for macOS:")
        print("  1. Tkinter is usually included with Python on macOS")
        print("  2. If missing, reinstall Python from python.org")
        print("  3. Or install via Homebrew:")
        print("     brew install python-tk@3.11")
        print("     (adjust version to match your Python version)")
    
    elif system == "Windows":
        print("Installation instructions for Windows:")
        print("  1. Tkinter is usually included with Python on Windows")
        print("  2. If missing, reinstall Python from python.org")
        print("  3. During installation, ensure 'tcl/tk and IDLE' is checked")
    
    else:
        print(f"Unknown operating system: {system}")
        print("Please install tkinter for your Python installation")
    
    print("\nAfter installation, run this script again.")
    print("=" * 70)
    sys.exit(1)

import socket
import ipaddress
import urllib.request
import urllib.error
import json
import threading
import os
import http.client
from typing import List, Optional, Dict, Callable

class ProgressHTTPConnection(http.client.HTTPConnection):
    """HTTP connection that reports upload progress."""
    
    def __init__(self, *args, **kwargs):
        self.progress_callback = kwargs.pop('progress_callback', None)
        super().__init__(*args, **kwargs)
    
    def send(self, data):
        """Override send to track progress."""
        if self.progress_callback and hasattr(data, '__len__'):
            total_size = len(data)
            chunk_size = 8192  # 8KB chunks
            sent = 0
            
            # Convert data to bytes if it's a string
            if isinstance(data, str):
                data = data.encode('iso-8859-1')
            
            while sent < total_size:
                chunk = data[sent:sent + chunk_size]
                super().send(chunk)
                sent += len(chunk)
                self.progress_callback(sent, total_size)
        else:
            super().send(data)

class ProgressHTTPHandler(urllib.request.HTTPHandler):
    """HTTP handler that uses ProgressHTTPConnection."""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        super().__init__()
        self.progress_callback = progress_callback
    
    def http_open(self, req):
        return self.do_open(self._get_connection, req)
    
    def _get_connection(self, host, timeout=None):
        return ProgressHTTPConnection(host, timeout=timeout, progress_callback=self.progress_callback)

class OpenEVSEUploader:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenEVSE Firmware Uploader")
        self.root.resizable(True, True)
        
        self.firmware_path = tk.StringVar()
        self.target_ip = tk.StringVar()
        self.found_devices = []
        self.scanning = False
        
        self.create_widgets()
        
        # Auto-size window to fit content, then set minimum size
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth() + 20  # Add padding
        height = self.root.winfo_reqheight() + 20
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(width, height)
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for proper expansion
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Firmware Selection Section
        ttk.Label(main_frame, text="Firmware Selection", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(main_frame, text="Firmware File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.firmware_path, state='readonly').grid(
            row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(main_frame, text="Browse...", command=self.browse_firmware).grid(
            row=1, column=2, sticky=tk.E, pady=5, padx=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Device Selection Section
        ttk.Label(main_frame, text="Target Device", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        
        # Auto-discover frame
        discover_frame = ttk.LabelFrame(main_frame, text="Auto-Discover", padding="5")
        discover_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.scan_button = ttk.Button(discover_frame, text="Scan Network", command=self.start_scan)
        self.scan_button.grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.scan_status = ttk.Label(discover_frame, text="Click 'Scan Network' to find devices")
        self.scan_status.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # Device list
        ttk.Label(discover_frame, text="Found Devices:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0), padx=5)
        
        list_frame = ttk.Frame(discover_frame)
        list_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.device_listbox = tk.Listbox(list_frame, height=6, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.device_listbox.yview)
        
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)
        
        ttk.Button(discover_frame, text="Use Selected Device", command=self.use_selected_device).grid(
            row=3, column=0, columnspan=2, pady=5)
        
        # Manual entry frame
        manual_frame = ttk.LabelFrame(main_frame, text="Manual Entry", padding="5")
        manual_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(manual_frame, text="IP Address or Hostname:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.manual_entry = ttk.Entry(manual_frame, textvariable=self.target_ip, width=30)
        self.manual_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(manual_frame, text="Verify", command=self.verify_manual_entry).grid(
            row=0, column=2, sticky=tk.W, padx=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Upload Section
        ttk.Label(main_frame, text="Upload", font=('Arial', 10, 'bold')).grid(
            row=7, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='determinate', length=400, maximum=100)
        self.progress.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready to upload", foreground="blue")
        self.status_label.grid(row=9, column=0, columnspan=3, pady=5)
        
        # Upload button
        self.upload_button = ttk.Button(main_frame, text="Upload Firmware", 
                                       command=self.start_upload, style='Accent.TButton')
        self.upload_button.grid(row=10, column=0, columnspan=3, pady=10)
        
    def browse_firmware(self):
        filename = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[
                ("Binary Files", "*.bin"),
                ("All Files", "*.*")
            ]
        )
        if filename:
            self.firmware_path.set(filename)
            
    def get_local_network(self) -> Optional[ipaddress.IPv4Network]:
        """Detect the local network range."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            return network
        except Exception:
            return None
            
    def get_hostname(self, ip: str) -> str:
        """Get hostname from OpenEVSE device config API."""
        try:
            url = f"http://{ip}/config"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    hostname = data.get('hostname') or data.get('device_name') or data.get('name')
                    if hostname:
                        return hostname
        except Exception:
            pass
        
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except (socket.herror, socket.gaierror, socket.timeout):
            return "(unknown)"
    
    def check_host(self, ip: str) -> Optional[Dict]:
        """Check if a host has Mongoose server on port 80."""
        try:
            url = f"http://{ip}"
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=2) as response:
                server_header = response.headers.get('Server', '')
                
                if 'Mongoose' in server_header:
                    hostname = self.get_hostname(ip)
                    return {
                        'ip': ip,
                        'hostname': hostname,
                        'server': server_header
                    }
        except Exception:
            pass
        
        return None
    
    def scan_network_thread(self):
        """Scan network for OpenEVSE devices using parallel threads."""
        self.scanning = True
        self.found_devices = []
        
        network = self.get_local_network()
        if not network:
            self.root.after(0, lambda: self.scan_status.config(
                text="Error: Could not detect network"))
            self.scanning = False
            self.root.after(0, lambda: self.scan_button.config(state='normal'))
            return
        
        self.root.after(0, lambda: self.scan_status.config(
            text=f"Scanning {network}..."))
        
        hosts = list(network.hosts())
        checked = [0]  # Use list to make it mutable in nested function
        lock = threading.Lock()
        
        def check_and_update(ip_str):
            if not self.scanning:
                return
            
            result = self.check_host(ip_str)
            
            with lock:
                checked[0] += 1
                current = checked[0]
                
                if result:
                    self.found_devices.append(result)
                    display_text = f"{result['ip']} - {result['hostname']}"
                    self.root.after(0, lambda t=display_text: self.device_listbox.insert(tk.END, t))
                
                if current % 25 == 0 or current == len(hosts):
                    self.root.after(0, lambda c=current, t=len(hosts): 
                        self.scan_status.config(text=f"Scanning... {c}/{t} hosts checked"))
        
        # Use thread pool for parallel scanning
        max_workers = 50
        threads = []
        
        for ip in hosts:
            if not self.scanning:
                break
            
            thread = threading.Thread(target=check_and_update, args=(str(ip),), daemon=True)
            thread.start()
            threads.append(thread)
            
            # Limit concurrent threads
            if len(threads) >= max_workers:
                threads[0].join()
                threads.pop(0)
        
        # Wait for remaining threads
        for thread in threads:
            thread.join()
        
        count = len(self.found_devices)
        self.root.after(0, lambda: self.scan_status.config(
            text=f"Scan complete: Found {count} device(s)"))
        self.scanning = False
        self.root.after(0, lambda: self.scan_button.config(state='normal'))
    
    def start_scan(self):
        """Start network scan in background thread."""
        self.device_listbox.delete(0, tk.END)
        self.found_devices = []
        self.scan_button.config(state='disabled')
        self.scan_status.config(text="Preparing to scan...")
        
        thread = threading.Thread(target=self.scan_network_thread, daemon=True)
        thread.start()
    
    def on_device_select(self, event):
        """Handle device selection from listbox."""
        pass  # Selection handled by use_selected_device button
    
    def use_selected_device(self):
        """Use the selected device from the listbox."""
        selection = self.device_listbox.curselection()
        if selection:
            idx = selection[0]
            if idx < len(self.found_devices):
                device = self.found_devices[idx]
                self.target_ip.set(device['ip'])
                messagebox.showinfo("Device Selected", 
                    f"Selected: {device['hostname']} ({device['ip']})")
        else:
            messagebox.showwarning("No Selection", "Please select a device from the list")
    
    def verify_manual_entry(self):
        """Verify manually entered IP/hostname."""
        target = self.target_ip.get().strip()
        
        if not target:
            messagebox.showwarning("Empty Address", "Please enter an IP address or hostname")
            return
        
        # Show verification in progress
        self.status_label.config(text=f"Verifying {target}...", foreground="blue")
        
        def verify_thread():
            result = self.check_host(target)
            
            if result:
                self.root.after(0, lambda: messagebox.showinfo("Device Found", 
                    f"OpenEVSE device verified!\n\n"
                    f"IP: {result['ip']}\n"
                    f"Hostname: {result['hostname']}\n"
                    f"Server: {result['server']}\n\n"
                    f"Ready to upload firmware."))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ Device verified: {result['hostname']}", foreground="green"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("Device Not Found", 
                    f"Could not find OpenEVSE device at {target}\n\n"
                    f"Please check:\n"
                    f"- The address is correct\n"
                    f"- The device is powered on\n"
                    f"- You are on the same network\n\n"
                    f"You can still try uploading anyway."))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"⚠ Could not verify device at {target}", foreground="orange"))
        
        thread = threading.Thread(target=verify_thread, daemon=True)
        thread.start()
    
    def upload_firmware_thread(self, firmware_path: str, target: str):
        """Upload firmware in background thread."""
        try:
            # Read firmware file
            with open(firmware_path, 'rb') as f:
                firmware_data = f.read()
            
            file_size = len(firmware_data)
            filename = os.path.basename(firmware_path)
            
            self.root.after(0, lambda: self.status_label.config(
                text=f"Uploading {filename} ({file_size:,} bytes)...", foreground="blue"))
            
            # Prepare multipart form data
            boundary = '----WebKitFormBoundary' + os.urandom(16).hex()
            
            body = []
            body.append(f'--{boundary}'.encode())
            body.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
            body.append(b'Content-Type: application/octet-stream')
            body.append(b'')
            body.append(firmware_data)
            body.append(f'--{boundary}--'.encode())
            body.append(b'')
            
            body_bytes = b'\r\n'.join(body)
            total_size = len(body_bytes)
            
            # Progress callback to update the progress bar
            def update_progress(sent: int, total: int):
                percent = int((sent / total) * 100)
                def set_progress():
                    self.progress['value'] = percent
                    self.status_label.config(
                        text=f"Uploading {filename}: {percent}% ({sent:,}/{total:,} bytes)", 
                        foreground="blue")
                self.root.after(0, set_progress)
            
            # Upload firmware with progress tracking
            url = f"http://{target}/update"
            req = urllib.request.Request(url, data=body_bytes, method='POST')
            req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
            req.add_header('Content-Length', str(total_size))
            
            # Create opener with progress handler
            opener = urllib.request.build_opener(ProgressHTTPHandler(progress_callback=update_progress))
            
            with opener.open(req, timeout=120) as response:
                result = response.read().decode()
                
                if response.status == 200:
                    self.root.after(0, lambda: self.show_success(target))
                else:
                    self.root.after(0, lambda: self.show_error(
                        f"Upload failed with status {response.status}"))
        
        except urllib.error.URLError as e:
            self.root.after(0, lambda: self.show_error(f"Network error: {e.reason}"))
        except FileNotFoundError:
            self.root.after(0, lambda: self.show_error("Firmware file not found"))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(f"Error: {str(e)}"))
        finally:
            self.root.after(0, self.upload_complete)
    
    def show_success(self, target: str):
        """Show success message."""
        self.status_label.config(
            text="✓ Firmware uploaded successfully! Device is rebooting...", 
            foreground="green")
        messagebox.showinfo("Upload Successful", 
            f"Firmware uploaded successfully to {target}!\n\n"
            "The device will now reboot and apply the update.\n"
            "This may take 30-60 seconds.")
    
    def show_error(self, message: str):
        """Show error message."""
        self.status_label.config(text=f"✗ {message}", foreground="red")
        messagebox.showerror("Upload Failed", message)
    
    def upload_complete(self):
        """Reset UI after upload completes."""
        self.progress['value'] = 0
        self.upload_button.config(state='normal')
    
    def start_upload(self):
        """Start firmware upload."""
        firmware = self.firmware_path.get()
        target = self.target_ip.get().strip()
        
        # Validate inputs
        if not firmware:
            messagebox.showwarning("No Firmware", "Please select a firmware file")
            return
        
        if not os.path.exists(firmware):
            messagebox.showerror("File Not Found", "Selected firmware file does not exist")
            return
        
        if not target:
            messagebox.showwarning("No Target", 
                "Please select a device or enter an IP address/hostname")
            return
        
        # Confirm upload
        filename = os.path.basename(firmware)
        file_size = os.path.getsize(firmware)
        
        confirm = messagebox.askyesno("Confirm Upload",
            f"Upload firmware to {target}?\n\n"
            f"File: {filename}\n"
            f"Size: {file_size:,} bytes\n\n"
            "The device will reboot after upload.\n"
            "Do not power off during update!")
        
        if not confirm:
            return
        
        # Start upload
        self.upload_button.config(state='disabled')
        self.progress['value'] = 0
        self.status_label.config(text="Preparing upload...", foreground="blue")
        
        thread = threading.Thread(
            target=self.upload_firmware_thread, 
            args=(firmware, target),
            daemon=True)
        thread.start()

def main():
    root = tk.Tk()
    app = OpenEVSEUploader(root)
    root.mainloop()

if __name__ == "__main__":
    main()
