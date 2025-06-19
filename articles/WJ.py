import os
import shutil
import base64
import json
import http.server
import socketserver
import urllib.parse
from functools import partial
from hashlib import sha256

# 配置信息
PORT = 2222
PASSWORD_HASH = "ac0e7d037817094e9e0b4441f9bae3209d67b02fa484917065f71b16109a1a78"  # sha256("admin123456")
SESSION_COOKIE = "AUTH_COOKIE_12345"
WEB_ROOT = os.getcwd()

# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件管理器</title>
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }
        body { margin: 0; padding: 20px; background: #f0f2f5; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; }
        
        .auth-box { 
            background: white; 
            padding: 2rem; 
            border-radius: 10px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            width: 90%;
            max-width: 400px;
            margin: 100px auto;
        }
        
        .file-list {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 1rem;
        }
        
        .file-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        
        .file-item:hover { background: #f8f9fa; }
        
        .file-icon {
            width: 24px;
            height: 24px;
            margin-right: 12px;
            opacity: 0.6;
        }
        
        .file-name { 
            flex-grow: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 8px;
            transition: 0.2s;
        }
        
        .btn-primary { background: #007bff; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-success { background: #28a745; color: white; }
        
        .upload-box {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .error { color: #dc3545; margin-top: 8px; }
    </style>
</head>
<body>
    <div id="authBox" class="auth-box">
        <h2 style="text-align: center; margin-bottom: 1.5rem;">请登录小小博客后台管理系统</h2>
        <input type="password" id="password" placeholder="请输入密码" 
               style="width: 100%; padding: 8px; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 4px;"
               onkeypress="if(event.keyCode==13) login()"
               >
        <button onclick="login()" class="btn btn-primary" style="width: 100%;">登录</button>
        <div id="errorMsg" class="error"></div>
    </div>
    
    <div id="mainContent" style="display: none;">
        <div class="container">
            <div class="upload-box">
                <input type="file" id="fileInput"><-选择文件或拖入文件</input>
                <button onclick="uploadFile()" class="btn btn-success">上传文件</button>
                <button onclick="createFolder()" class="btn btn-primary">创建新文件夹</button>
                <a href=":8000"><button>返回博客主页</button></a>
            </div>
            
            <div class="file-list" id="fileList"></div>
        </div>
    </div>

    <script>
        let currentPath = '';
        
        async function login() {
            const password = document.getElementById('password').value;
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            
            if (response.ok) {
                document.getElementById('authBox').style.display = 'none';
                document.getElementById('mainContent').style.display = 'block';
                loadFiles();
            } else {
                document.getElementById('errorMsg').textContent = 'Invalid password';
            }
        }

        async function loadFiles(path = '') {
            currentPath = path;
            const response = await fetch(`/list?path=${encodeURIComponent(path)}`);
            const files = await response.json();
            
            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';
            
            if (path) {
                const upItem = createItem('📁 ..', '', true);
                upItem.onclick = () => loadFiles(path.split('/').slice(0, -1).join('/'));
                fileList.appendChild(upItem);
            }
            
            files.forEach(file => {
                const item = createItem(
                    `${file.is_dir ? '📁' : '📄'} ${file.name}`,
                    file.name,
                    file.is_dir
                );
                
                if (file.is_dir) {
                    item.onclick = () => loadFiles(`${path}/${file.name}`);
                }
                
                fileList.appendChild(item);
            });
        }

        function createItem(text, name, isDir) {
            const div = document.createElement('div');
            div.className = 'file-item';
            div.innerHTML = `
                <div class="file-name">${text}</div>
                ${!isDir ? `<button class="btn btn-primary" onclick="downloadFile('${name}')">下载</button>` : ''}
                <button class="btn btn-danger" onclick="deleteItem('${name}', ${isDir})">删除</button>
                <button class="btn btn-primary" onclick="renameItem('${name}')">重命名</button>
            `;
            return div;
        }

        async function deleteItem(name, isDir) {
            if (!confirm(`Delete ${isDir ? 'folder' : 'file'} "${name}"?`)) return;
            await fetch(`/delete?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name)}&is_dir=${isDir}`, { method: 'POST' });
            loadFiles(currentPath);
        }

        async function renameItem(oldName) {
            const newName = prompt('Enter new name:', oldName);
            if (newName && newName !== oldName) {
                await fetch(`/rename?path=${encodeURIComponent(currentPath)}&old=${encodeURIComponent(oldName)}&new=${encodeURIComponent(newName)}`, { method: 'POST' });
                loadFiles(currentPath);
            }
        }

        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            await fetch(`/upload?path=${encodeURIComponent(currentPath)}`, {
                method: 'POST',
                body: formData
            });
            
            fileInput.value = '';
            loadFiles(currentPath);
        }

        async function createFolder() {
            const name = prompt('Enter folder name:');
            if (name) {
                await fetch(`/mkdir?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name)}`, { method: 'POST' });
                loadFiles(currentPath);
            }
        }

        function downloadFile(name) {
            window.location.href = `/download?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name)}`;
        }
    </script>
</body>
</html>
"""

class FileRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            if not self.check_auth():
                return self.send_login_page()
            self.send_html(HTML_TEMPLATE)
        elif self.path.startswith('/download'):
            self.handle_download()
        elif self.path.startswith('/list'):
            self.handle_list()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/login':
            self.handle_login()
        elif self.path.startswith('/delete'):
            self.handle_delete()
        elif self.path.startswith('/rename'):
            self.handle_rename()
        elif self.path.startswith('/upload'):
            self.handle_upload()
        elif self.path.startswith('/mkdir'):
            self.handle_mkdir()
        else:
            self.send_error(404)

    def check_auth(self):
        return self.headers.get('Cookie') == f'session={SESSION_COOKIE}'

    def send_login_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

    def send_html(self, content):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        input_hash = sha256(post_data['password'].encode()).hexdigest()
        
        if input_hash == PASSWORD_HASH:
            self.send_response(200)
            self.send_header('Set-Cookie', f'session={SESSION_COOKIE}')
            self.end_headers()
        else:
            self.send_response(401)
            self.end_headers()

    def handle_list(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        target = os.path.join(WEB_ROOT, path.strip('/'))
        
        if not os.path.exists(target):
            return self.send_error(404)
            
        files = []
        for name in os.listdir(target):
            full_path = os.path.join(target, name)
            files.append({
                'name': name,
                'is_dir': os.path.isdir(full_path),
                'size': os.path.getsize(full_path)
            })
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(files).encode())

    def handle_delete(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        name = query.get('name', [''])[0]
        is_dir = query.get('is_dir', [''])[0] == 'True'
        
        target = os.path.join(WEB_ROOT, path.strip('/'), name)
        if is_dir:
            shutil.rmtree(target)
        else:
            os.remove(target)
        self.send_response(200)
        self.end_headers()

    def handle_rename(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        old_name = query.get('old', [''])[0]
        new_name = query.get('new', [''])[0]
        
        old_path = os.path.join(WEB_ROOT, path.strip('/'), old_name)
        new_path = os.path.join(WEB_ROOT, path.strip('/'), new_name)
        os.rename(old_path, new_path)
        self.send_response(200)
        self.end_headers()

    def handle_upload(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        upload_dir = os.path.join(WEB_ROOT, path.strip('/'))
        
        content_type = self.headers['Content-Type']
        if not content_type.startswith('multipart/form-data'):
            return self.send_error(400)
            
        form_data = self.rfile.read(int(self.headers['Content-Length']))
        boundary = content_type.split('boundary=')[1]
        parts = form_data.split(b'--' + boundary.encode())
        
        for part in parts:
            if b'Content-Disposition: form-data; name="file"' in part:
                header, content = part.split(b'\r\n\r\n', 1)
                filename = header.split(b'filename="')[1].split(b'"')[0].decode()
                file_content = content
                
                with open(os.path.join(upload_dir, filename), 'wb') as f:
                    f.write(file_content)
        
        self.send_response(200)
        self.end_headers()

    def handle_mkdir(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        name = query.get('name', [''])[0]
        
        new_dir = os.path.join(WEB_ROOT, path.strip('/'), name)
        os.makedirs(new_dir, exist_ok=True)
        self.send_response(200)
        self.end_headers()

    def handle_download(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        path = query.get('path', [''])[0]
        name = query.get('name', [''])[0]
        
        target = os.path.join(WEB_ROOT, path.strip('/'), name)
        if not os.path.exists(target):
            return self.send_error(404)
            
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename="{name}"')
        self.end_headers()
        
        with open(target, 'rb') as f:
            shutil.copyfileobj(f, self.wfile)

if __name__ == '__main__':
    import socket
    def get_internal_ip():
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname_ex(hostname)[-1][0]
        except:
            return "无法获取内网IP"

    internal_ip = get_internal_ip()
    
    with socketserver.TCPServer(("0.0.0.0", PORT), FileRequestHandler) as httpd:
        print(f"\n{'='*40}")
        print(f"本地访问地址: http://127.0.0.1:{PORT}")
        print(f"内网访问地址: http://{internal_ip}:{PORT}")
        print(f"{'='*40}\n")
        httpd.serve_forever()

