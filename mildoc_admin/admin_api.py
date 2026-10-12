# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import json
from dotenv import load_dotenv
from functools import wraps
from oss_api import list_oss_object_info_by_dir, get_oss_object_info, upload_oss_object_from_bytes, download_oss_object, delete_oss_object
from urllib.parse import unquote, quote
from vector_api import get_doc_fragments
from flask import Response
import io
from smq_api import send_oss_update_event
from conversation_api import list_messages as conversation_list_messages, list_customer_info_recently
import redis
from flask_session import Session
# from totp import verify_totp

# 加载环境变量
load_dotenv()


# 管理员账号
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

OSS_BUCKET = os.getenv('OSS_BUCKET')
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

FLASK_SESSION_REDIS_URL = os.getenv('FLASK_SESSION_REDIS_URL')

app = Flask(__name__)


# 配置 Redis
redis_store = redis.from_url(FLASK_SESSION_REDIS_URL)

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_store
app.config['SESSION_PERMANENT'] = False # 如果需要，可以设置 session 为永久
app.config['SESSION_USE_SIGNER'] = True # 对 session id 进行签名
app.config['SECRET_KEY'] = FLASK_SECRET_KEY # 用于签名 session id 的密钥

app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# 初始化 Flask-Session
Session(app)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    """在每个请求之前执行"""
    if request.url.startswith('/api/'):
        app.logger.info(f"api请求: {request.url}")


@app.route('/')
def index():
    """首页，重定向到登录页面或文件浏览页面"""
    if 'username' in session:
        return redirect(url_for('file_browser'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # totp_code = request.form['totp_code']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['username'] = username
            flash('登录成功！', 'success')
            return redirect(url_for('file_browser'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录"""
    session.pop('username', None)
    flash('已退出登录', 'info')
    return redirect(url_for('login'))


# 文件浏览页面
@app.route('/files')
@login_required
def file_browser():
    """文件浏览页面"""
    return render_template('file_browser.html')

# 文件详情页面
@app.route('/file/<path:file_path>')
@login_required
def file_detail(file_path):
    """文件详情页面"""
    return render_template('file_detail.html')


# 活跃客户列表页面
@app.route('/customers')
@login_required
def customer_browser():
    """活跃客户列表页面，展示最近 100 个活跃客户"""
    customers = list_customer_info_recently(limit=100)
    return render_template('customer_browser.html', customers=customers)


# 对话浏览页面，URL: /conversation?external_userid=&start_id=&limit=
@app.route('/conversation')
@login_required
def conversation_browser():
    """对话浏览页面"""
    return render_template('conversation_browser.html')


# 获取对话消息列表 API
@app.route('/api/conversation/messages')
@login_required
def api_conversation_messages():
    """获取对话消息列表 API，支持 external_userid、start_id、limit"""
    try:
        external_userid = request.args.get('external_userid', '').strip() or None
        start_id_arg = request.args.get('start_id', '')
        start_id = int(start_id_arg) if start_id_arg != '' else -1
        limit = min(int(request.args.get('limit', 20)), 100)
        if limit <= 0:
            limit = 20
        messages, next_start_id = conversation_list_messages(start_id=start_id, limit=limit, external_userid=external_userid)

        app.logger.info(f"获取对话消息列表: external_userid={external_userid}, start_id={start_id}, limit={limit}, next_start_id={next_start_id}")
        rows = []
        for m in messages:
            msgbody = m.msgbody if isinstance(m.msgbody, dict) else (json.loads(m.msgbody) if isinstance(m.msgbody, str) else {})
            content = msgbody.get('content', '') if isinstance(msgbody, dict) else ''
            rows.append({
                'id': m.id,
                'msgid': m.msgid,
                'open_kfid': m.open_kfid,
                'external_userid': m.external_userid,
                'servicer_userid': m.servicer_userid or '',
                'send_time': m.send_time,
                'origin': m.origin,
                'msgtype': m.msgtype,
                'content': content,
            })
        return jsonify({'messages': rows, 'next_start_id': next_start_id})
    except ValueError as e:
        return jsonify({'error': f'参数错误: {e}'}), 400
    except Exception as e:
        app.logger.error(f"获取对话消息失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 获取文件列表 API
@app.route('/api/files')
@login_required
def api_files():
    """获取文件列表 API"""
    path = request.args.get('path', '')
    files = []
    try:
        sub_docs = list_oss_object_info_by_dir(OSS_BUCKET, path)

        for sub_doc in sub_docs:
            files.append({
                'name': sub_doc.doc_name,
                'path': sub_doc.doc_path,
                'type': 'file' if not sub_doc.is_dir else 'folder',
                'size': sub_doc.doc_length,
                'modified': sub_doc.last_modified.strftime('%Y-%m-%d %H:%M:%S') if sub_doc.last_modified else ''
            })
        
        return jsonify({'files': files})
    except Exception as e:
        app.logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({'error': f'获取文件列表失败: {str(e)}'}), 500


# 获取文件详情 API
@app.route('/api/file/<path:file_path>')
@login_required
def api_file_detail(file_path):
    """获取文件详情 API"""
    try:
        # URL 解码文件路径
        file_path = unquote(file_path)
        doc_info = get_oss_object_info(OSS_BUCKET, file_path)
        if not doc_info:
            return jsonify({'error': f'文件不存在: {file_path}'}), 404
        file_info = {
            'doc_name': doc_info.doc_name,
            'doc_path_name': doc_info.doc_path,
            'file_size': doc_info.doc_length,
            'file_md5': doc_info.doc_md5,
            'doc_type': doc_info.doc_type,
            'last_modified': doc_info.last_modified.strftime('%Y-%m-%d %H:%M:%S'),
            'indexed': False,
            'index_time': '',
            'chunks': []
        }

        doc_fragments = get_doc_fragments(file_path)

        chunks = []
        for doc_fragment in doc_fragments:
            chunks.append({
                'content': doc_fragment,
                'length': len(doc_fragment)
            })
        file_info['chunks'] = chunks
        file_info['indexed'] = len(doc_fragments) > 0
        file_info['index_time'] = ''

        return jsonify(file_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 上传文件 API
@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload_files():
    """文件上传 API"""
    try:
        # 获取上传路径
        upload_path = request.form.get('path', '')
        upload_path = upload_path.rstrip('/')
        # 检查是否有文件
        if 'files' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': '没有选择有效的文件'}), 400
        
        app.logger.info(f"开始上传 {len(files)} 个文件到路径: {upload_path}")
        
        uploaded_files = []
        failed_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # 构建完整的对象路径
                if upload_path:
                    object_name = f"{upload_path}/{file.filename}"
                else:
                    object_name = file.filename
                
                upload_oss_object_from_bytes(OSS_BUCKET, object_name, file)

                uploaded_files.append({
                    'filename': file.filename,
                    'object_name': object_name
                })
                
                app.logger.info(f"文件上传成功: {object_name}")
                
            except Exception as e:
                app.logger.error(f"上传文件 {file.filename} 失败: {str(e)}")
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        # 构造返回结果
        result = {
            'success': len(uploaded_files) > 0,
            'uploaded_count': len(uploaded_files),
            'failed_count': len(failed_files),
            'uploaded_files': uploaded_files,
            'failed_files': failed_files,
            'message': f'成功上传 {len(uploaded_files)} 个文件'
        }
        
        if failed_files:
            result['message'] += f'，{len(failed_files)} 个文件上传失败'
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"文件上传处理失败: {str(e)}")
        return jsonify({'error': f'文件上传处理失败: {str(e)}'}), 500


# 文件下载 API
@app.route('/api/file/<path:file_path>/download')
@login_required
def api_download_file(file_path):
    """文件下载 API"""
    try:
        # URL 解码文件路径
        file_path = unquote(file_path)
        
        app.logger.info(f"下载文件: {file_path}")
        
        file_data, content_type, filename, length = download_oss_object(OSS_BUCKET, file_path)

        encoded_filename = quote(filename)
        
        return Response(
            file_data,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename*=UTF-8\'\'{encoded_filename}',
                'Content-Length': str(length),
                'Cache-Control': 'no-cache'
            }
        )
    except Exception as e:
        app.logger.error(f"下载文件失败: {str(e)}")
        return jsonify({'error': f'下载文件失败: {str(e)}'}), 500


# 文件索引 API
@app.route('/api/file/<path:file_path>/index', methods=['POST'])
@login_required
def api_index_file(file_path):
    """文件索引 API"""
    try:
        file_path = unquote(file_path)
        send_oss_update_event(OSS_BUCKET, file_path)
        return jsonify({'success': True, 'message': '文件索引请求发送成功'})
    except Exception as e:
        app.logger.error(f"发送文件索引请求失败: {str(e)}")
        return jsonify({'error': f'发送文件索引请求失败: {str(e)}'}), 500

# 文件删除 API
@app.route('/api/file/<path:file_path>/delete', methods=['DELETE'])
@login_required
def api_delete_file(file_path):
    """文件删除 API"""
    try:
        # URL 解码文件路径
        file_path = unquote(file_path)
        
        app.logger.info(f"删除文件: {file_path}")
        
        delete_oss_object(OSS_BUCKET, file_path)
        app.logger.info(f"文件删除成功: {file_path}")
                
        return jsonify({
            'success': True,
            'message': f'文件 "{file_path}" 删除成功',
            'file_name': os.path.basename(file_path),
            'file_path': file_path
        })
    except Exception as e:
        app.logger.error(f"删除文件失败: {str(e)}")
        return jsonify({'error': f'删除文件失败: {str(e)}'}), 500

# 创建目录 API
@app.route('/api/create-directory', methods=['POST'])
@login_required
def api_create_directory():
    """创建目录 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        current_path = data.get('path', '')
        dir_name = data.get('name', '').strip()
        
        # 验证目录名称
        if not dir_name:
            return jsonify({'success': False, 'error': '目录名称不能为空'}), 400
        
        # 检查非法字符
        import re
        if re.search(r'[/\\:*?"<>|]', dir_name):
            return jsonify({'success': False, 'error': '目录名称不能包含以下字符: / \\ : * ? " < > |'}), 400
        
        # 构建完整路径
        if current_path:
            full_path = current_path.rstrip('/') + '/' + dir_name + '/'
        else:
            full_path = dir_name + '/'
        
        app.logger.info(f"创建目录: {full_path}")
        
        upload_oss_object_from_bytes(OSS_BUCKET, full_path, io.BytesIO(b''))
        
        app.logger.info(f"目录创建成功: {full_path}")
        return jsonify({'success': True, 'message': '目录创建成功'})
        
    except Exception as e:
        app.logger.error(f"创建目录失败: {str(e)}")
        return jsonify({'success': False, 'error': f'创建目录失败: {str(e)}'}), 500

# 删除目录 API
@app.route('/api/delete-directory', methods=['DELETE'])
@login_required
def api_delete_directory():
    """删除目录 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        dir_path = data.get('path', '').strip()
        
        # 验证路径
        if not dir_path:
            return jsonify({'success': False, 'error': '目录路径不能为空'}), 400
        
        # 确保路径以 / 结尾
        if not dir_path.endswith('/'):
            dir_path += '/'
        
        app.logger.info(f"删除目录: {dir_path}")
        
        sub_docs= list_oss_object_info_by_dir(OSS_BUCKET, dir_path)
        if sub_docs:
            return jsonify({'success': False, 'error': '目录不为空，无法删除'}), 400
        
        delete_oss_object(OSS_BUCKET, dir_path)
        
        app.logger.info(f"目录删除成功: {dir_path}")
        return jsonify({'success': True, 'message': '目录删除成功'})
    except Exception as e:
        app.logger.error(f"删除目录失败: {str(e)}")
        return jsonify({'success': False, 'error': f'删除目录失败: {str(e)}'}), 500


if __name__ == '__main__':
    
    # 获取主机和端口配置
    host = os.getenv('FLASK_HOST')
    port = int(os.getenv('FLASK_PORT'))


    print("=" * 60)
    print("Mildoc 管理后台启动中...")
    print(f"访问端口: {port}")
    print("=" * 60)
    
    app.run(
        host=host,
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=True,
        processes=1
    ) 
