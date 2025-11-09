from flask import Flask, render_template, request, redirect, url_for, flash, make_response, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_babel import Babel, gettext as _
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
from functools import wraps
import paypalrestsdk

# 初始化Flask应用
app = Flask(__name__, instance_relative_config=False)
# 配置：加密密钥（替换成你自己的随机字符串）
app.config['SECRET_KEY'] = 'dfgadgdf!!j5273424'
PAYPAL_CONFIG = {
    "mode": "sandbox",  # 测试用sandbox，正式上线改为live
    "client_id": "Ab5jXf9FWR8ToLsYwWjXXd4qtzGT2OJ8ZhgiKa4G1AXutqsXC07xAo4McpIViLKspYXbW75vSbXLTUW8",  # 替换成你的Client ID
    "client_secret": "EPd2i8uKqeESK_JHW0tNmHcLWVDd5hOixS7d84VJwnWPeXqep4A5VPSbk4AdXWLqOp5rwavklpZpvdas"   # 替换成你的Secret
}
paypalrestsdk.configure(PAYPAL_CONFIG)  # 初始化PayPal SDK

# 配置数据库（PostgreSQL连接字符串）
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://baifan7574:IJJDniMHTMaLProNANQaIp8uGU9qT0nn@dpg-d471vq7diees73dgdd90-a/tools_8956'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭不必要的警告

# 修复：移除错误的引擎配置参数（dialect和drivername由连接字符串自动识别）
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True  # 仅保留连接检查，确保连接有效性
}

# 配置多语言
app.config['LANGUAGES'] = {'zh': '中文', 'en': 'English'}
# 打印连接字符串（验证是否正确）
print("实际使用的数据库连接字符串：", app.config['SQLALCHEMY_DATABASE_URI'])

# 初始化数据库
db = SQLAlchemy(app)
# 初始化登录管理
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# 初始化多语言
babel = Babel(app)

# 全局变量：记录IP访问次数（防刷）
ip_access_counts = {}


# 1. 数据库模型
class User(UserMixin, db.Model):
    __tablename__ = 'users'  # 显式指定表名
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # 哈希密码字段
    is_vip = db.Column(db.Boolean, default=False)
    vip_expire = db.Column(db.DateTime)
    trial_uses = db.Column(db.Integer, default=10)
    invite_code = db.Column(db.String(20), unique=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 外键关联users表
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_invite_code(self):
        # 生成随机邀请码（6位字母数字）
        import random
        import string
        self.invite_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan = db.Column(db.String(20))  # month/year/lifetime
    amount = db.Column(db.Float)
    pay_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_success = db.Column(db.Boolean, default=False)


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tool_name = db.Column(db.String(50))
    file_name = db.Column(db.String(100))
    handle_time = db.Column(db.DateTime, default=datetime.utcnow)


class UploadHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_name = db.Column(db.String(100))
    file_size = db.Column(db.Integer)  # 字节
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)


# 2. 通用工具函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 多语言配置
def get_locale():
    return request.cookies.get('lang', 'zh')
babel.locale_selector_func = get_locale

# 试用次数检查
def check_trial_usage():
    if not current_user.is_authenticated:
        return _("请先登录才能使用工具！")
    if current_user.is_vip:
        return None
    if current_user.trial_uses <= 0:
        return _("您的免费试用次数已用完，请升级会员继续使用！")
    current_user.trial_uses -= 1
    db.session.commit()
    return None


# IP访问限制装饰器
def limit_ip(limit=10):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            ip_access_counts[ip] = ip_access_counts.get(ip, 0) + 1
            if ip_access_counts[ip] > limit:
                return _("操作频繁，请稍后再试"), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator


# 3. 路由
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/text-tools', methods=['GET', 'POST'])
def text_tools():
    if request.method == 'POST':
        # 检查试用次数
        error_msg = check_trial_usage()
        if error_msg:
            return render_template('text_tools.html', message=error_msg)
        
        # 检查文件
        uploaded_file = request.files.get('file')
        if not uploaded_file or uploaded_file.filename == '':
            return render_template('text_tools.html', message=_("请先上传TXT文件！"))
        
        file_size = uploaded_file.content_length
        max_size = 10*1024*1024 if current_user.is_vip else 1*1024*1024
        if file_size > max_size:
            return render_template('text_tools.html', 
                                 message=_("文件太大！免费用户限1MB，会员限10MB"))
        
        # 工具处理逻辑
        tool_name = request.form.get('tool_name')
        try:
            if tool_name == 'remove_duplicate':
                from tools.text_tool import remove_duplicate_lines
                result_stream, msg = remove_duplicate_lines(uploaded_file)
                filename = _("去重后的文本.txt")
            
            elif tool_name == 'count_words':
                from tools.count_text_words import count_text_words
                result_stream, msg = count_text_words(uploaded_file)
                filename = _("文本统计结果.txt")
            
            elif tool_name == 'convert_newline':
                from tools.text_newline import convert_newline
                mode = request.form.get('newline_mode', 'linux')
                result_stream, msg = convert_newline(uploaded_file, convert_to=mode)
                filename = _("换行符转换后的文本.txt")
            
            elif tool_name == 'extract_keywords':
                from tools.text_keyword import extract_keywords
                top_n = int(request.form.get('top_n', 10))
                result_stream, msg = extract_keywords(uploaded_file, top_n=top_n)
                filename = _("文本关键词结果.txt")
            
            elif tool_name == 'convert_case':
                from tools.text_case import convert_case
                case_mode = request.form.get('case_mode', 'lower')
                result_stream, msg = convert_case(uploaded_file, case_mode=case_mode)
                filename = _("大小写转换后的文本.txt")
            
            elif tool_name == 'clean_spaces':
                from tools.text_clean import clean_spaces_empty_lines
                result_stream, msg = clean_spaces_empty_lines(uploaded_file)
                filename = _("去空格空行后的文本.txt")
            
            elif tool_name == 'batch_replace':
                from tools.text_replace import batch_replace
                old_str = request.form.get('old_str', '')
                new_str = request.form.get('new_str', '')
                result_stream, msg = batch_replace(uploaded_file, old_str, new_str)
                filename = _("批量替换后的文本.txt")
            
            elif tool_name == 'sort_lines':
                from tools.text_sort import sort_lines
                sort_mode = request.form.get('sort_mode', 'asc')
                is_number = request.form.get('is_number', 'false') == 'true'
                result_stream, msg = sort_lines(uploaded_file, sort_mode=sort_mode, is_number=is_number)
                filename = _("按行排序后的文本.txt")
            
            elif tool_name == 'extract_lines':
                from tools.text_extract_lines import extract_lines
                extract_mode = request.form.get('extract_mode', 'keyword')
                keyword = request.form.get('keyword', '')
                n = int(request.form.get('n', 10))
                if extract_mode == 'keyword':
                    result_stream, msg = extract_lines(uploaded_file, extract_mode=extract_mode, keyword=keyword)
                else:
                    result_stream, msg = extract_lines(uploaded_file, extract_mode=extract_mode, n=n)
                filename = _("提取指定行后的文本.txt")
            
            elif tool_name == 'split_cn_en':
                from tools.text_split_cn_en import split_cn_en
                result_stream, msg = split_cn_en(uploaded_file)
                filename = _("中英文分离后的文本.txt")
            
            else:
                return render_template('text_tools.html', message=_("工具不存在！"))
            
            if result_stream:
                # 记录历史
                new_history = History(
                    user_id=current_user.id,
                    tool_name=tool_name,
                    file_name=filename
                )
                db.session.add(new_history)
                # 记录上传历史
                new_upload = UploadHistory(
                    user_id=current_user.id,
                    file_name=uploaded_file.filename,
                    file_size=file_size
                )
                db.session.add(new_upload)
                db.session.commit()
                
                return send_file(
                    result_stream,
                    mimetype="text/plain",
                    as_attachment=True,
                    download_name=filename
                )
            else:
                return render_template('text_tools.html', message=msg)
        
        except Exception as e:
            return render_template('text_tools.html', message=f"{_('处理失败')}：{str(e)}")
    
    return render_template('text_tools.html')


@app.route('/register', methods=['GET', 'POST'])
@limit_ip(limit=10)
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        inviter_code = request.form.get('inviter_code', '')
        print(f"[注册调试] 收到表单：用户名={username}，邀请码={inviter_code}")
        
        # 检查用户名重复
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(_('用户名已被注册，请换一个'))
            return redirect('/register')
        
        # 创建新用户
        new_user = User(username=username)
        new_user.set_password(password)
        new_user.generate_invite_code()  # 生成邀请码
        print(f"[注册调试] 新用户创建：{new_user.username}，邀请码={new_user.invite_code}")
        
        # 处理邀请码
        if inviter_code:
            inviter = User.query.filter_by(invite_code=inviter_code).first()
            if inviter:
                new_user.inviter_id = inviter.id
                inviter.trial_uses += 5
                flash(_('通过邀请码注册成功，邀请者获得5次试用奖励'))
        
        # 提交到数据库
        db.session.add(new_user)
        try:
            db.session.commit()
            print("[注册调试] 数据库提交成功")
            flash(_('注册成功，请登录'))
            return redirect('/login')
        except Exception as e:
            db.session.rollback()  # 出错时回滚
            print(f"[注册调试] 数据库提交失败：{str(e)}")
            flash(_('注册失败：数据库错误，请稍后再试'))
            return redirect('/register')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@limit_ip(limit=50)
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect('/text-tools')
        flash(_('用户名或密码错误'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('已退出登录'))
    return redirect('/')


@app.route('/vip')
def vip():
    return render_template('vip.html')


# 支付相关路由（保持不变）
@app.route('/pay/paypal/month')
@login_required
def paypal_pay_month():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('paypal_success_month', _external=True),
            "cancel_url": url_for('vip', _external=True)
        },
        "transactions": [{
            "amount": {"total": "4.99", "currency": "USD"},
            "description": f"Monthly VIP: User ID={current_user.id}"
        }]
    })
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('月度支付链接创建失败，请稍后再试'))
    return redirect('/vip')


@app.route('/pay/paypal/annual')
@login_required
def paypal_pay_annual():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('paypal_success_annual', _external=True),
            "cancel_url": url_for('vip', _external=True)
        },
        "transactions": [{
            "amount": {"total": "47.88", "currency": "USD"},
            "description": f"Annual VIP: User ID={current_user.id}"
        }]
    })
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('年度支付链接创建失败，请稍后再试'))
    return redirect('/vip')


@app.route('/pay/paypal/lifetime')
@login_required
def paypal_pay_lifetime():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('paypal_success_lifetime', _external=True),
            "cancel_url": url_for('vip', _external=True)
        },
        "transactions": [{
            "amount": {"total": "199.00", "currency": "USD"},
            "description": f"Lifetime VIP: User ID={current_user.id}"
        }]
    })
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('终身支付链接创建失败，请稍后再试'))
    return redirect('/vip')


@app.route('/pay/success/month')
def paypal_success_month():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    if not payment_id or not payer_id:
        flash(_('支付信息不完整，请重新支付'))
        return redirect('/vip')
    payment = paypalrestsdk.Payment.find(payment_id)
    description = payment.transactions[0].description
    try:
        user_id = int(description.split('=')[-1])
        user = User.query.get(user_id)
    except:
        flash(_('支付信息解析失败，请联系管理员'))
        return redirect('/vip')
    if user and payment.execute({"payer_id": payer_id}):
        user.is_vip = True
        user.vip_expire = datetime.utcnow() + timedelta(days=30)
        new_payment = Payment(user_id=user.id, plan="month", amount=4.99, is_success=True)
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', vip_expire=user.vip_expire.strftime('%Y-%m-%d'), plan="月度会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')


@app.route('/pay/success/annual')
def paypal_success_annual():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    if not payment_id or not payer_id:
        flash(_('支付信息不完整，请重新支付'))
        return redirect('/vip')
    payment = paypalrestsdk.Payment.find(payment_id)
    description = payment.transactions[0].description
    try:
        user_id = int(description.split('=')[-1])
        user = User.query.get(user_id)
    except:
        flash(_('支付信息解析失败，请联系管理员'))
        return redirect('/vip')
    if user and payment.execute({"payer_id": payer_id}):
        user.is_vip = True
        user.vip_expire = datetime.utcnow() + timedelta(days=365)
        new_payment = Payment(user_id=user.id, plan="annual", amount=47.88, is_success=True)
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', vip_expire=user.vip_expire.strftime('%Y-%m-%d'), plan="年度会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')


@app.route('/pay/success/lifetime')
def paypal_success_lifetime():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    if not payment_id or not payer_id:
        flash(_('支付信息不完整，请重新支付'))
        return redirect('/vip')
    payment = paypalrestsdk.Payment.find(payment_id)
    description = payment.transactions[0].description
    try:
        user_id = int(description.split('=')[-1])
        user = User.query.get(user_id)
    except:
        flash(_('支付信息解析失败，请联系管理员'))
        return redirect('/vip')
    if user and payment.execute({"payer_id": payer_id}):
        user.is_vip = True
        user.vip_expire = datetime.utcnow() + timedelta(days=9999)
        new_payment = Payment(user_id=user.id, plan="lifetime", amount=199.00, is_success=True)
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', vip_expire=user.vip_expire.strftime('%Y-%m-%d'), plan="终身会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')


@app.route('/success')
def success():
    vip_expire = request.args.get('vip_expire', '未知')
    plan = request.args.get('plan', '会员')
    return render_template('success.html', vip_expire=vip_expire, plan=plan)


@app.route('/history')
@login_required
def history():
    if not current_user.is_vip:
        return redirect('/vip')
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.handle_time.desc()).all()
    return render_template('history.html', histories=histories)


@app.route('/invite')
@login_required
def invite():
    invited_users = User.query.filter_by(inviter_id=current_user.id).all()
    return render_template(
        'invite.html', 
        invite_code=current_user.invite_code,
        invited_count=len(invited_users)
    )


@app.route('/set-lang')
def set_lang():
    lang = request.args.get('lang', 'zh')
    response = make_response(redirect(request.referrer or '/'))
    response.set_cookie('lang', lang, max_age=30*24*3600)
    return response


# 底部页面路由
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/pay/callback', methods=['POST'])
def pay_callback():
    data = request.json
    if data.get('status') == 'success':
        user_id = data.get('user_id')
        plan = data.get('plan')
        user = User.query.get(user_id)
        if user:
            user.is_vip = True
            user.vip_expire = datetime.utcnow() + (timedelta(days=30) if plan == 'month' else timedelta(days=365))
            new_payment = Payment(
                user_id=user_id, plan=plan, amount=data.get('amount'), is_success=True
            )
            db.session.add(new_payment)
            db.session.commit()
            return "success"
    return "fail"


# 新增：管理员总览页面（合并用户和支付数据）
@app.route('/admin')
@login_required
def admin_dashboard():
    # 同时查询用户和支付数据
    users = User.query.all()
    payments = Payment.query.all()
    
    # 处理用户数据（整理成模板可用的格式）
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "is_vip": "是" if user.is_vip else "否",
            "vip_expire": user.vip_expire.strftime('%Y-%m-%d') if user.vip_expire else "未开通",
            "trial_uses": user.trial_uses,
            "invite_code": user.invite_code
        })
    
    # 处理支付数据（关联用户名）
    payment_list = []
    for pay in payments:
        user = User.query.get(pay.user_id)
        username = user.username if user else "未知用户"
        payment_list.append({
            "id": pay.id,
            "user_id": pay.user_id,
            "username": username,
            "plan": pay.plan,
            "amount": f"${pay.amount}",
            "pay_time": pay.pay_time.strftime('%Y-%m-%d %H:%M'),
            "is_success": "成功" if pay.is_success else "失败"
        })
    
    # 渲染到HTML模板
    return render_template('admin_dashboard.html', 
                         users=user_list, 
                         payments=payment_list)

# 关键修复：启用表结构创建逻辑（应用启动时自动创建所有表）
with app.app_context():
    print("开始创建表结构...")
    db.create_all()  # 自动创建所有模型对应的表
    print("表结构创建完成！")


if __name__ == '__main__':
    app.run(debug=True, port=10000)