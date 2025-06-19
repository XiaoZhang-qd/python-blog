import os
import re
import sys
import json
import socket
import argparse
import http.server
import socketserver
from string import Template
from datetime import datetime
from threading import Thread, Lock

# ============================================
# 获取本机内网IP地址和正在运行的脚本程序的名称
# ============================================
script_name = os.path.basename(sys.argv[0])

def internal_ip():
    try:
        hostname = socket.gethostname()
        _, _, ip_list = socket.gethostbyname_ex(hostname)

        # 增强过滤规则
        blacklist = []

        valid_ips = [
          ip for ip in ip_list
          if not any(ip.startswith(prefix) for prefix in blacklist)
          and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip)
        ]

        # 私有地址优先级排序
        private_ips = sorted(
          [ip for ip in valid_ips if re.match(r"(10\.|192\.168|172\.(1[6-9]|2\d|3[0-1]))", ip)],
          key=lambda x: (x.startswith("192.168"), x.startswith("10"))  # 192.168 优先
        )

        return private_ips[0] if private_ips else valid_ips[0] if valid_ips else "127.0.0.1"
    except Exception as e:
      return f"错误: {str(e)}"

# ========================
# 配置模板和全局变量
# ========================
INDEX_TEMPLATE = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
    <title>小Z的小小博客 | 思想记录空间</title>
    <style>
        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --background: #f8f9fa;
            --card-bg: #ffffff;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            background: var(--background);
            color: var(--primary-color);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .container {
            max-width: 1200px;
            width: 90%;
            margin: 2rem auto;
            flex: 1;
        }

        header {
            text-align: center;
            padding: 3rem 0;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        h1 {
            font-size: 2.5rem;
            letter-spacing: 2px;
            margin-bottom: 0.5rem;
        }

        .post-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            padding: 1rem;
        }

        .post-item {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 3px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
        }

        .post-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }

        .post-meta {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 1rem;
        }

        .locked {
            position: relative;
            background: linear-gradient(135deg, #fff3f3 0%, #f8f9fa 100%);
        }

        .locked::after {
            content: "🔒";
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.2rem;
        }

        .password-form {
            margin-top: auto;
            display: flex;
            gap: 0.5rem;
        }

        input[type="password"] {
            flex: 1;
            padding: 0.8rem;
            border: 2px solid #eee;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s;
        }

        input[type="password"]:focus {
            outline: none;
            border-color: var(--secondary-color);
        }

        button {
            padding: 0.8rem 1.5rem;
            background: var(--secondary-color);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.3s;
        }

        button:hover {
            background: #2980b9;
        }

        @media (max-width: 768px) {
            .container {
                width: 95%;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            .post-list {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>小Z的小小博客</h1>
            <p>记录思考与成长的点滴</p>
        </div>
    </header>

    <div class="container">
        <h2>精选文章</h2>
        <ul class="post-list">
            $posts
        </ul>
    </div>
</body>
</html>
''')

POST_TEMPLATE = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$title</title>
    <style>
        /* 基础重置 */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        /* 现代字体和渐变背景 */
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            line-height: 1.7;
            min-height: 100vh;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            color: #212529;
            display: flex;
            flex-direction: column;
        }

        /* 容器布局 */
        .container {
            max-width: 1200px;
            width: 90%;
            margin: 2rem auto;
            padding: 2rem;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            flex-grow: 1;
        }

        /* 响应式标题 */
        h1 {
            font-size: clamp(2rem, 5vw, 3rem);
            color: #2b2d42;
            margin-bottom: 1.5rem;
            position: relative;
            padding-bottom: 0.5rem;
            text-align: center;
        }

        h1::after {
            content: "";
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 3px;
            background: #4a4e69;
        }

        /* 内容区域 */
        .content {
            font-size: clamp(1rem, 2vw, 1.1rem);
            color: #495057;
            margin: 2rem 0;
        }

        /* 返回链接样式 */
        .back-link {
            margin-bottom: 2rem;
            transition: transform 0.2s;
        }

        .back-link a {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            color: #4a4e69;
            font-weight: 500;
            padding: 0.75rem 1.5rem;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 50px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
        }

        .back-link a:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
            background: #fff;
        }

        /* 响应式图片 */
        img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 1.5rem 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }

        /* 移动端优化 */
        @media (max-width: 768px) {
            .container {
                width: 95%;
                padding: 1.5rem;
                margin: 1rem auto;
            }

            .back-link a {
                padding: 0.5rem 1rem;
                font-size: 0.9rem;
            }

            h1::after {
                width: 60px;
            }
        }

        @media (max-width: 480px) {
            body {
                padding: 0;
            }

            .container {
                border-radius: 0;
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="back-link">
            <a href="/">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
                </svg>
                返回首页
            </a>
        </div>
        
        <h1>$title</h1>
        <div class="content">
            $content
        </div>
    </div>
</body>
</html>
''')



##PASSWORD_TEMPLATE = Template('''
##<!DOCTYPE html>
##<html>
##<head>
##    <meta charset="UTF-8">
##    <meta name="viewport" content="width=device-width, initial-scale=1.0">
##    <title>需要密码</title>
##    <style>
##        body { max-width: 500px; margin: 50px auto; padding: 20px; }
##        form { border: 1px solid #ccc; padding: 20px; }
##        input[type="password"] { width: 200px; padding: 5px; }
##    </style>
##</head>
##<body>
##    <h2>该文章需要密码</h2>
##    <form method="GET" action="$post_url">
##        <input type="password" name="p" placeholder="输入访问密码">
##        <button type="submit">提交</button>
##    </form>
##</body>
##</html>
##''')

# ========================
# 核心功能类
# ========================
class BlogSystem:
    def __init__(self):
        self.articles_dir = "articles"
        self.passwords = {}
        self.lock = Lock()
        self.load_passwords()
    
    def load_passwords(self):
        try:
            with open('passwords.json', 'r') as f:
                with self.lock:
                    self.passwords = json.load(f)
        except FileNotFoundError:
            pass
    
    def save_passwords(self):
        with open('passwords.json', 'w') as f:
            with self.lock:
                json.dump(self.passwords, f)
    
    def set_password(self, article, password):
        with self.lock:
            self.passwords[article] = password
        self.save_passwords()
    
    def delete_password(self, article):
        with self.lock:
            if article in self.passwords:
                del self.passwords[article]
        self.save_passwords()
    
    def verify_password(self, article, input_pwd):
        with self.lock:
            return self.passwords.get(article) == input_pwd

# ========================
# HTTP请求处理
# ========================
class SecureBlogHandler(http.server.SimpleHTTPRequestHandler):
    blog = BlogSystem()

    def parse_query(self):
        query = {}
        if '?' in self.path:
            path, query_str = self.path.split('?', 1)
            for pair in query_str.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    query[k] = v
        return query

    def render_template(self, template, **kwargs):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(template.substitute(**kwargs).encode())

    def do_GET(self):
        query = self.parse_query()
        
        # 首页处理
        if self.path == '/':
            posts = []
            for filename in os.listdir(self.blog.articles_dir):
                if filename.endswith(('.md', '.html')):
                    article_name = os.path.splitext(filename)[0]
                    is_locked = article_name in self.blog.passwords
                    posts.append(f'''
                        <li class="post-item {'locked' if is_locked else ''}">
                            <a href="/post/{article_name}">{filename}</a>
                            {'🔒' if is_locked else ''}
                        </li>
                    ''')
            self.render_template(INDEX_TEMPLATE, posts='\n'.join(posts))
        
        # 文章页处理
        elif self.path.startswith("/post/"):
            article_name = self.path[6:].split('?')[0]
            filepath = None
            for ext in ['.md', '.html']:
                if os.path.exists(f'{self.blog.articles_dir}/{article_name}{ext}'):
                    filepath = f'{self.blog.articles_dir}/{article_name}{ext}'
                    break
            
            if not filepath:
                self.send_response(307)
                self.send_header('Location', '/')
                self.end_headers()
                return

            # 密码验证逻辑
            ##if article_name in self.blog.passwords:
                input_pwd = query.get('p', '')
                if not self.blog.verify_password(article_name, input_pwd):
                    self.render_template(PASSWORD_TEMPLATE, 
                                      post_url=f"/post/{article_name}")
                    return

            # 内容渲染逻辑
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if filepath.endswith('.md'):
                content = self.parse_markdown(content)
            
            self.render_template(POST_TEMPLATE, 
                               title=article_name, 
                               content=content)

    def parse_markdown(self, text):
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1">', text)
        return text.replace('\n', '<br>')

# ========================
# 命令行管理界面
# ========================
##def password_manager(blog):
##    help_msg = """
##    密码管理系统命令：
##    list       - 列出所有受保护文章
##    set <文章> <密码> - 设置密码
##    del <文章>   - 删除密码
##    exit       - 退出程序
##    """
##    print(help_msg)
##    
##    while True:
##        try:
##            cmd = input("> ").strip().split()
##            if not cmd:
##                continue
##                
##            if cmd[0] == "list":
##                print("受保护文章列表：")
##                for article in blog.passwords:
##                    print(f"  {article}: {blog.passwords[article]}")
##                    
##            elif cmd[0] == "set" and len(cmd) >=3:
##                blog.set_password(cmd[1], cmd[2])
##                print(f"已为文章 {cmd[1]} 设置密码")
##                
##            elif cmd[0] in ("del", "delete") and len(cmd)>=2:
##                blog.delete_password(cmd[1])
##               print(f"已删除文章 {cmd[1]} 的密码")
##                
##            elif cmd[0] == "exit":
##                os._exit(0)
##                
##            else:
##                print("无效命令")
##                
##        except Exception as e:
##            print(f"错误: {e}")

# ========================
# 主程序
# ========================
def main():
    print(f"当前脚本名称：{script_name}")
    parser = argparse.ArgumentParser(description="小小的博客系统")
    parser.add_argument('--host', default='0.0.0.0', help='绑定地址 (0.0.0.0 为内网访问)')
    parser.add_argument('--port', type=int, default=8000, help='监听端口')
    args = parser.parse_args()

    os.makedirs("articles", exist_ok=True)
    
    # 启动密码管理线程
    ##blog = SecureBlogHandler.blog
    ##t = Thread(target=password_manager, args=(blog,))
    ##t.daemon = True
    ##t.start()

    # 启动HTTP服务器
    with socketserver.TCPServer((args.host, args.port), SecureBlogHandler) as httpd:
        print(f"服务器已启动：http://127.0.0.1:{args.port}")
        print(f"内网访问地址：http://{internal_ip()}:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()
            print("\n服务器已关闭\n按下回程键结束...")
            exit (1)

if __name__ == "__main__":
    main()

