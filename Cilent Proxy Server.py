import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
import struct
import datetime
import urllib.parse
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler


class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.proxy_server = kwargs.pop('proxy_server', None)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_index_page()
        elif self.path.startswith('/proxy'):
            self.handle_proxy_request()
        else:
            self.send_error(404, 'Not Found')
    
    def do_POST(self):
        if self.path.startswith('/proxy'):
            self.handle_proxy_request()
        else:
            self.send_error(404, 'Not Found')
    
    def send_index_page(self):
        html_content = self.generate_index_page()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def generate_index_page(self):
        server_ip = self.proxy_server.local_ip if hasattr(self.proxy_server, 'local_ip') else '127.0.0.1'
        html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cilent Proxy</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px 20px;
            display: flex;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .server-ip {
            color: white;
            font-size: 14px;
            white-space: nowrap;
        }
        .address-bar-container {
            flex: 1;
            display: flex;
            justify-content: center;
            padding: 0 20px;
        }
        .address-bar {
            display: flex;
            width: 100%;
            max-width: 800px;
        }
        .address-bar input {
            flex: 1;
            padding: 12px 15px;
            border: none;
            border-radius: 8px 0 0 8px;
            font-size: 14px;
            outline: none;
        }
        .address-bar button {
            padding: 12px 25px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 0 8px 8px 0;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }
        .address-bar button:hover {
            background: #45a049;
        }
        .logo {
            color: white;
            font-size: 18px;
            font-weight: bold;
            white-space: nowrap;
        }
        .content {
            flex: 1;
            padding: 20px;
            overflow: auto;
        }
        #content-frame {
            width: 100%;
            height: 100%;
            border: none;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            min-height: 500px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 50px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="server-ip">服务器IP: ''' + server_ip + '''</div>
        <div class="address-bar-container">
            <div class="address-bar">
                <input type="text" id="url-input" placeholder="请输入要访问的网址 (例如: https://www.example.com)" />
                <button onclick="visitUrl()">访问</button>
            </div>
        </div>
        <div class="logo">Cilent Proxy</div>
    </div>
    <div class="content">
        <div class="loading" id="loading">加载中...</div>
        <iframe id="content-frame"></iframe>
    </div>
    <script>
        function visitUrl() {
            const urlInput = document.getElementById('url-input');
            const contentFrame = document.getElementById('content-frame');
            const loading = document.getElementById('loading');
            let url = urlInput.value.trim();
            
            if (!url) {
                alert('请输入网址');
                return;
            }
            
            loading.style.display = 'block';
            contentFrame.style.display = 'none';
            
            fetch('/proxy?url=' + encodeURIComponent(url))
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.text();
                })
                .then(html => {
                    contentFrame.srcdoc = html;
                    loading.style.display = 'none';
                    contentFrame.style.display = 'block';
                })
                .catch(error => {
                    loading.innerHTML = '加载失败: ' + error.message;
                });
        }
        
        document.getElementById('url-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                visitUrl();
            }
        });
    </script>
</body>
</html>
        '''
        return html
    
    def handle_proxy_request(self):
        try:
            url = None
            if self.command == 'GET':
                parsed_path = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_path.query)
                url = query_params.get('url', [None])[0]
            
            if not url:
                self.send_error(400, 'URL parameter is required')
                return
            
            response_data = self.proxy_server.fetch_url(url)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(response_data)
        except Exception as e:
            self.send_error(500, str(e))
    
    def log_message(self, format, *args):
        pass


class CilentProxyServer:
    def __init__(self, root):
        self.root = root
        self.root.title('Cilent Proxy | 服务端')
        self.root.geometry('800x600')
        
        self.server_socket = None
        self.service_running = False
        self.clients = {}
        self.clients_lock = threading.Lock()
        
        self.http_server = None
        self.local_ip = '127.0.0.1'
        
        self.create_widgets()
    
    def create_widgets(self):
        header_frame = tk.Frame(self.root, padx=10, pady=10)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(header_frame, text='Cilent Proxy 服务端', font=('Arial', 16, 'bold'))
        title_label.pack(side=tk.LEFT, padx=10)
        
        header_frame_left = tk.Frame(header_frame)
        header_frame_left.pack(side=tk.LEFT, expand=True)
        
        self.service_button = tk.Button(header_frame, text='启动服务', command=self.toggle_service, 
                                         bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), padx=15)
        self.service_button.pack(side=tk.RIGHT, padx=10)
        
        web_url_frame = tk.Frame(self.root, padx=10, pady=10)
        web_url_frame.pack(fill=tk.X)
        
        self.web_url_label = tk.Label(web_url_frame, text='访问地址：等待服务启动...', 
                                       font=('Arial', 10), fg='#2196F3', cursor='hand2')
        self.web_url_label.pack(side=tk.LEFT)
        
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        list_header_frame = tk.Frame(main_frame)
        list_header_frame.pack(fill=tk.X, pady=(0, 10))
        
        list_label = tk.Label(list_header_frame, text='已连接的客户端', font=('Arial', 12, 'bold'))
        list_label.pack(side=tk.LEFT)
        
        self.server_info_label = tk.Label(list_header_frame, text='服务器地址：等待中...', font=('Arial', 10))
        self.server_info_label.pack(side=tk.RIGHT)
        
        columns = ('client_id', 'ip', 'port', 'connected_time')
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('client_id', text='客户端 ID')
        self.tree.heading('ip', text='IP 地址')
        self.tree.heading('port', text='端口')
        self.tree.heading('connected_time', text='连接时间')
        
        self.tree.column('client_id', width=200)
        self.tree.column('ip', width=150)
        self.tree.column('port', width=100)
        self.tree.column('connected_time', width=200)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def toggle_service(self):
        if self.service_running:
            self.stop_service()
        else:
            self.start_service()
    
    def start_service(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            hostname = socket.gethostname()
            self.local_ip = socket.gethostbyname(hostname)
            self.server_socket.bind(('0.0.0.0', 8888))
            self.server_socket.listen(5)
            
            self.start_http_server()
            
            self.service_running = True
            self.service_button.config(text='停止服务', bg='#f44336')
            self.root.title('Cilent Proxy | 服务端 ({}:8888)'.format(self.local_ip))
            self.server_info_label.config(text='服务器地址：{}:8888'.format(self.local_ip))
            web_url = 'http://{}:8889'.format(self.local_ip)
            self.web_url_label.config(text='访问地址：{} (点击打开)'.format(web_url))
            self.web_url_label.bind('<Button-1>', lambda e: self.open_webpage(web_url))
            
            server_thread = threading.Thread(target=self.accept_clients, daemon=True)
            server_thread.start()
            
        except Exception as e:
            messagebox.showerror('Cilent Proxy', '启动服务失败：{}'.format(str(e)))
            if self.server_socket:
                self.server_socket.close()
            if self.http_server:
                self.http_server.shutdown()
    
    def start_http_server(self):
        def handler_factory(*args, **kwargs):
            return ProxyHTTPRequestHandler(*args, proxy_server=self, **kwargs)
        
        self.http_server = HTTPServer(('0.0.0.0', 8889), handler_factory)
        http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        http_thread.start()
    
    def open_webpage(self, url):
        import webbrowser
        webbrowser.open(url)
    
    def fetch_url(self, url):
        try:
            if url and not url.startswith(('http://', 'https://')):
                url = 'http://' + url
            
            parsed_url = urllib.parse.urlparse(url)
            host = parsed_url.hostname
            if not host:
                raise ValueError("无效的 URL 或 IP 地址")

            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            path = parsed_url.path or '/'
            if parsed_url.query:
                path += '?' + parsed_url.query
            
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            if parsed_url.scheme == 'https':
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                target_socket = context.wrap_socket(target_socket, server_hostname=host)
            
            target_socket.connect((host, port))
            
            request_lines = ['GET ' + path + ' HTTP/1.1']
            request_lines.append('Host: ' + host)
            request_lines.append('Connection: close')
            request_lines.append('User-Agent: Cilent Proxy/1.0')
            request_lines.append('Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
            request_lines.append('Accept-Language: zh-CN,zh;q=0.9,en;q=0.8')
            
            request = '\r\n'.join(request_lines) + '\r\n\r\n'
            
            target_socket.sendall(request.encode('utf-8'))
            
            response_data = b''
            while True:
                chunk = target_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            target_socket.close()
            
            if b'\r\n\r\n' in response_data:
                header_end = response_data.index(b'\r\n\r\n')
                body = response_data[header_end + 4:]
                return body
            
            return response_data
        except Exception as e:
            error_message = f'代理错误: {str(e)}' 
            print(f'Fetch URL Error: {error_message}')
            return ('<html><body><h1>代理错误</h1><p>{}</p></body></html>'.format(error_message)).encode('utf-8')
    
    def stop_service(self):
        self.service_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server = None
            except:
                pass
        
        with self.clients_lock:
            for client_id in list(self.clients.keys()):
                try:
                    self.clients[client_id]['socket'].close()
                except:
                    pass
                del self.clients[client_id]
        
        self.refresh_clients_list()
        self.service_button.config(text='启动服务', bg='#4CAF50')
        self.root.title('Cilent Proxy | 服务端')
        self.server_info_label.config(text='服务器地址：等待中...')
        self.web_url_label.config(text='访问地址：等待服务启动...')
        self.web_url_label.unbind('<Button-1>')
    
    def accept_clients(self):
        while self.service_running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client_socket, client_address = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_client, 
                                                      args=(client_socket, client_address), 
                                                      daemon=True)
                    client_thread.start()
                except socket.timeout:
                    continue
            except:
                if self.service_running:
                    break
    
    def handle_client(self, client_socket, client_address):
        client_id = None
        try:
            while self.service_running:
                data = self.receive_data(client_socket)
                if not data:
                    break
                
                if data.get('type') == 'hello':
                    client_id = data.get('client_id')
                    connected_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    with self.clients_lock:
                        self.clients[client_id] = {
                            'socket': client_socket,
                            'ip': client_address[0],
                            'port': client_address[1],
                            'connected_time': connected_time
                        }
                    
                    self.refresh_clients_list()
                    
                    response = {'type': 'hello_ack', 'status': 'ok'}
                    self.send_data(client_socket, response)
                
                elif data.get('type') == 'request':
                    self.handle_proxy_request(client_socket, data)
        
        except Exception as e:
            print('客户端处理错误：{}'.format(e))
        finally:
            if client_id:
                with self.clients_lock:
                    if client_id in self.clients:
                        try:
                            self.clients[client_id]['socket'].close()
                        except:
                            pass
                        del self.clients[client_id]
                self.refresh_clients_list()
            else:
                try:
                    client_socket.close()
                except:
                    pass
    
    def handle_proxy_request(self, client_socket, request_data):
        try:
            t_url = request_data.get('url', '')
            t_method = request_data.get('method', 'GET')
            t_headers = request_data.get('headers', {})
            t_body = request_data.get('body', '')
            
            print(f'Handling proxy request: {t_method} {t_url}')
            
            # --- 自动补全协议头，防止只输入 IP 或域名导致解析失败 ---
            if t_url and not t_url.startswith(('http://', 'https://')):
                t_url = 'http://' + t_url
            
            parsed_url = urllib.parse.urlparse(t_url)
            host = parsed_url.hostname
            # 如果解析后仍然没有 host，可能是输入了完全无效的字符串
            if not host:
                raise ValueError("无效的 URL 或 IP 地址")

            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            path = parsed_url.path or '/'
            if parsed_url.query:
                path += '?' + parsed_url.query
            
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            if parsed_url.scheme == 'https':
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                target_socket = context.wrap_socket(target_socket, server_hostname=host)
            
            target_socket.connect((host, port))
            
            request_lines = [t_method + ' ' + path + ' HTTP/1.1']
            request_lines.append('Host: ' + host)
            request_lines.append('Connection: close')
            request_lines.append('User-Agent: Cilent Proxy/1.0')
            
            for key, value in t_headers.items():
                if key.lower() not in ['host', 'connection']:
                    request_lines.append(key + ': ' + value)
            
            request = '\r\n'.join(request_lines) + '\r\n\r\n'
            if t_body:
                request += t_body
            
            target_socket.sendall(request.encode('utf-8'))
            
            response_data = b''
            while True:
                chunk = target_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            target_socket.close()
            
            response = {
                'type': 'response',
                'status': 200,
                'headers': {},
                'body': response_data.hex()
            }
            
            self.send_data(client_socket, response)
            print(f'Request completed successfully: {t_url}')
        except Exception as e:
            error_message = f'代理错误：{str(e)}'
            print(f'Proxy request error: {error_message}')
            error_response = {
                'type': 'response',
                'status': 500,
                'headers': {'Content-Type': 'text/plain'},
                'body': error_message.encode('utf-8').hex()
            }
            self.send_data(client_socket, error_response)
    
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
    
    def refresh_clients_list(self):
        self.root.after(0, self._refresh_clients_list)
    
    def _refresh_clients_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        with self.clients_lock:
            for client_id, client_info in self.clients.items():
                self.tree.insert('', tk.END, values=(
                    client_id,
                    client_info['ip'],
                    client_info['port'],
                    client_info['connected_time']
                ))


def main():
    root = tk.Tk()
    app = CilentProxyServer(root)
    root.mainloop()


if __name__ == '__main__':
    main()