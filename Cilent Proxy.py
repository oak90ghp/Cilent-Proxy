import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
import threading
import datetime
import json
import struct
import os
import urllib.parse  # 新增：用于解析用户输入的复杂URL


class CilentProxyClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Cilent Proxy | 客户端")
        self.root.geometry("900x600")
        
        self.servers = []
        self.connected_server = None
        self.service_running = False
        self.proxy_socket = None
        self.load_servers()
        
        self.create_menu()
        self.create_widgets()
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="选项", menu=options_menu)
        options_menu.add_command(label="设置", command=self.open_settings)
    
    def create_widgets(self):
        header_frame = tk.Frame(self.root, padx=10, pady=10)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(header_frame, text="Cilent Proxy 客户端", font=("Arial", 16, "bold"))
        title_label.pack(side=tk.LEFT, padx=10)
        
        header_frame_left = tk.Frame(header_frame)
        header_frame_left.pack(side=tk.LEFT, expand=True)
        
        self.service_button = tk.Button(header_frame, text="开启服务", command=self.toggle_service, 
                                         bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), padx=15)
        self.service_button.pack(side=tk.RIGHT, padx=10)
        
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        list_header_frame = tk.Frame(main_frame)
        list_header_frame.pack(fill=tk.X, pady=(0, 10))
        
        list_label = tk.Label(list_header_frame, text="服务器列表", font=("Arial", 12, "bold"))
        list_label.pack(side=tk.LEFT)
        
        add_server_button = tk.Button(list_header_frame, text="添加服务器", command=self.add_server_dialog, 
                                       bg="#2196F3", fg="white", font=("Arial", 10))
        add_server_button.pack(side=tk.RIGHT)
        
        columns = ("name", "ip", "url", "added_time")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)
        
        self.tree.heading("name", text="名称")
        self.tree.heading("ip", text="服务器IP")
        self.tree.heading("url", text="连接地址")
        self.tree.heading("added_time", text="添加时间")
        
        self.tree.column("name", width=150)
        self.tree.column("ip", width=150)
        self.tree.column("url", width=300)
        self.tree.column("added_time", width=150)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.refresh_servers_list()
    
    def open_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("400x300")
        
        label = tk.Label(settings_window, text="设置界面 (稍后补充)", font=("Arial", 12))
        label.pack(pady=20)
    
    def add_server_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("添加服务器")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="名称：", font=("Arial", 10)).grid(row=0, column=0, padx=10, pady=15, sticky=tk.W)
        name_entry = tk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=15)
        
        # 将提示文案改为更精确的描述
        tk.Label(dialog, text="服务器地址\n(IP/域名)：", font=("Arial", 10)).grid(row=1, column=0, padx=10, pady=15, sticky=tk.W)
        url_entry = tk.Entry(dialog, width=30)
        url_entry.grid(row=1, column=1, padx=10, pady=15)
        
        def add_server():
            name = name_entry.get().strip()
            raw_url = url_entry.get().strip()
            
            if not name or not raw_url:
                messagebox.showwarning("Cilent Proxy", "请填写所有字段！")
                return
            
            # --- 智能提取纯净的主机名或IP，防止用户输入 http:// 或端口号导致报错 ---
            clean_host = raw_url
            if "://" in clean_host:
                clean_host = urllib.parse.urlparse(clean_host).hostname
            
            if clean_host and ":" in clean_host:
                clean_host = clean_host.split(":")[0]
                
            if not clean_host:
                clean_host = raw_url
            # -------------------------------------------------------------

            try:
                # gethostbyname 原生支持纯净的 IP 或域名
                ip = socket.gethostbyname(clean_host)
            except socket.gaierror:
                messagebox.showerror("Cilent Proxy", f"无法解析服务器地址：{clean_host}\n请确保输入的是正确的IP或域名！")
                return
            
            added_time = datetime.datetime.now().strftime("%Y年%m月%d日")
            
            server = {
                "name": name,
                "ip": ip,
                "url": clean_host,  # 这里保存纯净的地址，供后续 socket.connect 使用
                "added_time": added_time
            }
            
            self.servers.append(server)
            self.save_servers()
            self.refresh_servers_list()
            dialog.destroy()
        
        button_frame = tk.Frame(dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        tk.Button(button_frame, text="添加", command=add_server, bg="#4CAF50", fg="white", padx=20).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="取消", command=dialog.destroy, bg="#f44336", fg="white", padx=20).pack(side=tk.LEFT, padx=10)
    
    def refresh_servers_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for server in self.servers:
            self.tree.insert("", tk.END, values=(
                server["name"], 
                server["ip"], 
                server["url"], 
                server["added_time"]
            ))
    
    def save_servers(self):
        data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(self.servers, f, ensure_ascii=False, indent=2)
    
    def load_servers(self):
        data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        if os.path.exists(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    self.servers = json.load(f)
            except:
                self.servers = []
    
    def toggle_service(self):
        if self.service_running:
            self.stop_service()
        else:
            self.start_service()
    
    def start_service(self):
        if not self.servers:
            messagebox.showwarning("Cilent Proxy", "请先添加服务器！")
            return
        
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Cilent Proxy", "请选择一个服务器！")
            return
        
        item = self.tree.item(selected_items[0])
        server = None
        for s in self.servers:
            if s["url"] == item["values"][2]:
                server = s
                break
        
        if not server:
            return
        
        try:
            self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 这里连接我们提取好的纯净 URL（IP或域名），固定端口8888
            self.proxy_socket.connect((server["url"], 8888))
            
            hello_data = {"type": "hello", "client_id": "client_" + str(os.getpid())}
            self.send_data(self.proxy_socket, hello_data)
            
            response = self.receive_data(self.proxy_socket)
            if response and response.get("type") == "hello_ack":
                self.connected_server = server
                self.service_running = True
                self.service_button.config(text="停止服务", bg="#f44336")
                messagebox.showinfo("Cilent Proxy", "连接成功")
                
                proxy_thread = threading.Thread(target=self.proxy_loop, daemon=True)
                proxy_thread.start()
            else:
                messagebox.showerror("Cilent Proxy", "连接失败：服务端未返回确认")
                self.proxy_socket.close()
                
        except Exception as e:
            messagebox.showerror("Cilent Proxy", f"连接失败：{str(e)}\n请确认服务端是否已启动。")
            if self.proxy_socket:
                self.proxy_socket.close()
    
    def stop_service(self):
        self.service_running = False
        if self.proxy_socket:
            try:
                self.proxy_socket.close()
            except:
                pass
        self.service_button.config(text="开启服务", bg="#4CAF50")
    
    def send_data(self, sock, data):
        json_data = json.dumps(data).encode('utf-8')
        sock.sendall(struct.pack('!I', len(json_data)))
        sock.sendall(json_data)
    
    def receive_data(self, sock):
        try:
            length_data = sock.recv(4)
            if not length_data:
                return None
            length = struct.unpack('!I', length_data)[0]
            data = b''
            while len(data) < length:
                packet = sock.recv(length - len(data))
                if not packet:
                    return None
                data += packet
            return json.loads(data.decode('utf-8'))
        except:
            return None
    
    def proxy_loop(self):
        try:
            self.local_proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.local_proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.local_proxy_socket.bind(('127.0.0.1', 8080))
            self.local_proxy_socket.listen(10)
            
            self.root.after(0, lambda: messagebox.showinfo("Cilent Proxy", "本地代理已启动\n请将浏览器代理配置为：127.0.0.1:8080"))
            
            while self.service_running:
                try:
                    self.local_proxy_socket.settimeout(1.0)
                    try:
                        client_conn, client_addr = self.local_proxy_socket.accept()
                        client_thread = threading.Thread(target=self.handle_local_proxy_connection, 
                                                          args=(client_conn,), 
                                                          daemon=True)
                        client_thread.start()
                    except socket.timeout:
                        continue
                except Exception as e:
                    if self.service_running:
                        print(f"代理循环错误: {e}")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Cilent Proxy", f"本地代理启动失败: {str(e)}"))
        finally:
            try:
                self.local_proxy_socket.close()
            except:
                pass
            self.stop_service()
    
    def handle_local_proxy_connection(self, client_conn):
        try:
            request_data = client_conn.recv(4096)
            if not request_data:
                return
            
            request_lines = request_data.split(b'\r\n')
            if not request_lines:
                return
            
            first_line = request_lines[0].decode('utf-8', errors='ignore')
            parts = first_line.split()
            if len(parts) < 3:
                return
            
            method = parts[0]
            url = parts[1]
            version = parts[2]
            
            if method == 'CONNECT':
                self.handle_https_tunnel(client_conn, url)
                return
            
            if not url.startswith('http'):
                host_line = None
                for line in request_lines[1:]:
                    if line.lower().startswith(b'host:'):
                        host_line = line
                        break
                
                if host_line:
                    host = host_line.split(b':', 1)[1].strip().decode('utf-8')
                    url = f'http://{host}{url}'
            
            headers = {}
            for line in request_lines[1:]:
                if b':' in line:
                    key, value = line.split(b':', 1)
                    headers[key.decode('utf-8', errors='ignore').strip()] = value.decode('utf-8', errors='ignore').strip()
            
            body = b''
            if b'\r\n\r\n' in request_data:
                body_start = request_data.index(b'\r\n\r\n') + 4
                body = request_data[body_start:]
            
            proxy_request = {
                "type": "request",
                "url": url,
                "method": method,
                "headers": headers,
                "body": body.decode('utf-8', errors='ignore')
            }
            
            self.send_data(self.proxy_socket, proxy_request)
            proxy_response = self.receive_data(self.proxy_socket)
            
            if proxy_response and proxy_response.get("type") == "response":
                response_body = bytes.fromhex(proxy_response.get("body", ""))
                client_conn.sendall(response_body)
            
        except Exception as e:
            print(f"代理连接处理错误: {e}")
        finally:
            try:
                client_conn.close()
            except:
                pass
    
    def handle_https_tunnel(self, client_conn, host_port):
        try:
            client_conn.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            
            host, port = host_port.split(':')
            port = int(port)
            
            while self.service_running:
                client_conn.settimeout(0.5)
                try:
                    data = client_conn.recv(4096)
                    if not data:
                        break
                    
                    proxy_request = {
                        "type": "request",
                        "url": f"https://{host_port}",
                        "method": "TUNNEL",
                        "headers": {},
                        "body": data.hex()
                    }
                    
                    self.send_data(self.proxy_socket, proxy_request)
                    proxy_response = self.receive_data(self.proxy_socket)
                    
                    if proxy_response and proxy_response.get("type") == "response":
                        response_body = bytes.fromhex(proxy_response.get("body", ""))
                        client_conn.sendall(response_body)
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"HTTPS隧道处理错误: {e}")
        finally:
            try:
                client_conn.close()
            except:
                pass


def main():
    root = tk.Tk()
    app = CilentProxyClient(root)
    root.mainloop()


if __name__ == '__main__':
    main()


def main():
    root = tk.Tk()
    app = CilentProxyClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()