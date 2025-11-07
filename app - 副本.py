from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# 初始化Flask应用
app = Flask(__name__)
# 配置：加密密钥（随便写一串字符）
app.config['SECRET_KEY'] = 'fjsakl23498sdfklj234lkjsdf98'
# 配置数据库（数据存在site.db文件里）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭警告
# 初始化数据库
db = SQLAlchemy(app)
# 初始化登录管理
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 未登录时跳转到登录页


# 定义用户表（存储用户信息）
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # 唯一ID
    username = db.Column(db.String(50), unique=True, nullable=False)  # 用户名（不能重复）
    password_hash = db.Column(db.String(128), nullable=False)  # 加密后的密码
    is_vip = db.Column(db.Boolean, default=False)  # 是否会员（默认不是）
    vip_expire = db.Column(db.DateTime)  # 会员过期时间（默认为空）

    # 加密密码的方法
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # 验证密码的方法
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# 登录管理器需要的回调函数（通过用户ID获取用户）
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 路由1：首页（显示分类）
@app.route('/')
def index():
    return render_template('index.html')


# 路由2：文本工具页（显示工具+处理工具请求）
@app.route('/text-tools', methods=['GET', 'POST'])
def text_tools():
    if request.method == 'POST':
        # 工具处理逻辑（和之前完全一样，直接复用）
        tool_name = request.form.get('tool_name')
        uploaded_file = request.files.get('file')
        
        if not uploaded_file or uploaded_file.filename == '':
            return render_template('text_tools.html', message="请先上传TXT文件！")
        
        try:
            # 1. 文本去重
            if tool_name == 'remove_duplicate':
                from tools.text_tool import remove_duplicate_lines
                result_stream, msg = remove_duplicate_lines(uploaded_file)
                filename = "去重后的文本.txt"
            
            # 2. 字数统计
            elif tool_name == 'count_words':
                from tools.count_text_words import count_text_words
                result_stream, msg = count_text_words(uploaded_file)
                filename = "文本统计结果.txt"
            
            # 3. 换行符转换
            elif tool_name == 'convert_newline':
                from tools.text_newline import convert_newline
                mode = request.form.get('newline_mode', 'linux')
                result_stream, msg = convert_newline(uploaded_file, convert_to=mode)
                filename = "换行符转换后的文本.txt"
            
            # 4. 关键词提取
            elif tool_name == 'extract_keywords':
                from tools.text_keyword import extract_keywords
                top_n = int(request.form.get('top_n', 10))
                result_stream, msg = extract_keywords(uploaded_file, top_n=top_n)
                filename = "文本关键词结果.txt"
            
            # 5. 大小写转换
            elif tool_name == 'convert_case':
                from tools.text_case import convert_case
                case_mode = request.form.get('case_mode', 'lower')
                result_stream, msg = convert_case(uploaded_file, case_mode=case_mode)
                filename = "大小写转换后的文本.txt"
            
            # 6. 去空格/空行
            elif tool_name == 'clean_spaces':
                from tools.text_clean import clean_spaces_empty_lines
                result_stream, msg = clean_spaces_empty_lines(uploaded_file)
                filename = "去空格空行后的文本.txt"
            
            # 7. 批量替换
            elif tool_name == 'batch_replace':
                from tools.text_replace import batch_replace
                old_str = request.form.get('old_str', '')
                new_str = request.form.get('new_str', '')
                result_stream, msg = batch_replace(uploaded_file, old_str, new_str)
                filename = "批量替换后的文本.txt"
            
            # 8. 按行排序
            elif tool_name == 'sort_lines':
                from tools.text_sort import sort_lines
                sort_mode = request.form.get('sort_mode', 'asc')
                is_number = request.form.get('is_number', 'false') == 'true'
                result_stream, msg = sort_lines(uploaded_file, sort_mode=sort_mode, is_number=is_number)
                filename = "按行排序后的文本.txt"
            
            # 9. 提取指定行
            elif tool_name == 'extract_lines':
                from tools.text_extract_lines import extract_lines
                extract_mode = request.form.get('extract_mode', 'keyword')
                keyword = request.form.get('keyword', '')
                n = int(request.form.get('n', 10))
                if extract_mode == 'keyword':
                    result_stream, msg = extract_lines(uploaded_file, extract_mode=extract_mode, keyword=keyword)
                else:
                    result_stream, msg = extract_lines(uploaded_file, extract_mode=extract_mode, n=n)
                filename = "提取指定行后的文本.txt"
            
            # 10. 中英文分离
            elif tool_name == 'split_cn_en':
                from tools.text_split_cn_en import split_cn_en
                result_stream, msg = split_cn_en(uploaded_file)
                filename = "中英文分离后的文本.txt"
            
            else:
                return render_template('text_tools.html', message="工具不存在！")
            
            if result_stream:
                from flask import send_file
                return send_file(
                    result_stream,
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename
                )
            else:
                return render_template('text_tools.html', message=msg)
        
        except Exception as e:
            return render_template('text_tools.html', message=f"处理失败：{str(e)}")
    
    # GET请求：显示工具页面
    return render_template('text_tools.html')


# 路由3：注册页
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash('用户名已被注册，请换一个')
            return redirect('/register')
        # 创建新用户
        new_user = User(username=username)
        new_user.set_password(password)  # 加密密码
        db.session.add(new_user)
        db.session.commit()
        flash('注册成功，请登录')
        return redirect('/login')
    return render_template('register.html')


# 路由4：登录页
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)  # 登录用户
            return redirect('/text-tools')  # 登录后跳工具页
        flash('用户名或密码错误')
    return render_template('login.html')


# 路由5：登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录')
    return redirect('/')


# 路由6：会员支付页
@app.route('/vip')
def vip():
    return render_template('vip.html')


# 创建数据库表（首次运行时执行）
with app.app_context():
    db.create_all()  # 自动生成site.db文件


# 运行服务器
if __name__ == '__main__':
    app.run(debug=True, port=5001)  # 端口5001（避免冲突）