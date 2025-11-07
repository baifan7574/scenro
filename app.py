from flask import Flask, render_template, request, redirect, url_for, flash, make_response, send_file
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
app = Flask(__name__,instance_relative_config=False)
# 配置：加密密钥（替换成你自己的随机字符串）
app.config['SECRET_KEY'] = 'dfgadgdf!!j5273424'
PAYPAL_CONFIG = {
    "mode": "sandbox",  # 测试用sandbox，正式上线改为live
    "client_id": "Ab5jXf9FWR8ToLsYwWjXXd4qtzGT2OJ8ZhgiKa4G1AXutqsXC07xAo4McpIViLKspYXbW75vSbXLTUW8",  # 替换成你的Client ID
    "client_secret": "EPd2i8uKqeESK_JHW0tNmHcLWVDd5hOixS7d84VJwnWPeXqep4A5VPSbk4AdXWLqOp5rwavklpZpvdas"   # 替换成你的Secret
}
paypalrestsdk.configure(PAYPAL_CONFIG)  # 初始化PayPal SDK
# 配置数据库（数据存在site.db文件里）
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:100100@localhost:3306/tool_website?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭不必要的警告
# 配置多语言
app.config['LANGUAGES'] = {'zh': '中文', 'en': 'English'}
# 初始化数据库
db = SQLAlchemy(app)
# 初始化登录管理
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# 初始化多语言（兼容所有版本的写法）
babel = Babel(app)

# 全局变量：记录IP访问次数（防刷）
ip_access_counts = {}


# 1. 数据库模型
class User(UserMixin, db.Model):
    __tablename__ = 'users'  # 显式指定表名，避免复数转换不一致
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # 加长字段以容纳哈希值
    is_vip = db.Column(db.Boolean, default=False)
    vip_expire = db.Column(db.DateTime)
    trial_uses = db.Column(db.Integer, default=10)
    invite_code = db.Column(db.String(20), unique=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 外键关联正确表名（users）
    
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 修复：外键指向users.id
    plan = db.Column(db.String(20))  # month/year
    amount = db.Column(db.Float)
    pay_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_success = db.Column(db.Boolean, default=False)


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 修复：外键指向users.id
    tool_name = db.Column(db.String(50))
    file_name = db.Column(db.String(100))
    handle_time = db.Column(db.DateTime, default=datetime.utcnow)


class UploadHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 修复：外键指向users.id
    file_name = db.Column(db.String(100))
    file_size = db.Column(db.Integer)  # 字节
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)


# 2. 通用工具函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 兼容写法：用 babel 对象的 locale_selector 方法注册
def get_locale():
    return request.cookies.get('lang', 'zh')
babel.locale_selector_func = get_locale

# 试用次数检查（所有工具通用）
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
        
        # 检查文件大小
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
    
    # GET请求：显示工具页（带新手引导）
    return render_template('text_tools.html')

@app.route('/register', methods=['GET', 'POST'])
@limit_ip(limit=10)
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        inviter_code = request.form.get('inviter_code', '')  # 新增邀请码输入
        print(f"[注册调试] 收到表单：用户名={username}，密码={password},邀请码={inviter_code}")  # 日志1
       
        
        # 1. 检查用户名是否重复
        existing_user = User.query.filter_by(username=username).first()
        print(f"[注册调试] 用户名是否重复：{existing_user is not None}")  # 日志2
        if existing_user:
            flash(_('用户名已被注册，请换一个'))
            return redirect('/register')
        
        # 2. 创建新用户并加密密码
        new_user = User(username=username)
        new_user.set_password(password) 
        new_user.generate_invite_code()  # 补充：生成邀请码（之前漏掉了） # 必须调用此方法！
        print(f"[注册调试] 新用户创建成功：{new_user.username}，邀请码={new_user.invite_code}")  # 日志3
        if inviter_code:
            inviter = User.query.filter_by(invite_code=inviter_code).first()
            if inviter:
                new_user.inviter_id = inviter.id  # 现在new_user已存在，不会报错
                inviter.trial_uses += 5
                flash(_('通过邀请码注册成功，邀请者获得5次试用奖励'))
        
        # 3. 强制写入数据库（这两行是核心！）
        db.session.add(new_user)
        print("[注册调试] 已执行 db.session.add(new_user)")  # 日志4
        try:
            db.session.commit()
            print("[注册调试] 已执行 db.session.commit()，数据写入成功！")  # 日志5
            flash(_('注册成功，请登录'))
            return redirect('/login')
        except Exception as e:
            print(f"[注册调试] 数据库提交失败：{str(e)}")  # 关键错误日志
            flash(_('注册失败，请检查数据库权限或联系管理员'))
            return redirect('/register')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@limit_ip(limit=50)  # 同一IP最多登录5次
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
# 月度会员支付（$4.99/月）
@app.route('/pay/paypal/month')
@login_required
def paypal_pay_month():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('paypal_success_month', _external=True),  # 回调路由
            "cancel_url": url_for('vip', _external=True)
        },
        "transactions": [{
            "amount": {"total": "4.99", "currency": "USD"},  # 月度价格
            "description": f"Monthly VIP: User ID={current_user.id}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('月度支付链接创建失败，请稍后再试'))
    return redirect('/vip')
# 年度会员支付（$47.88/年）
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
            "amount": {"total": "47.88", "currency": "USD"},  # 年度价格
            "description": f"Annual VIP: User ID={current_user.id}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('年度支付链接创建失败，请稍后再试'))
    return redirect('/vip')

# 终身会员支付（$199.00/终身）
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
            "amount": {"total": "199.00", "currency": "USD"},  # 终身价格
            "description": f"Lifetime VIP: User ID={current_user.id}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)
    flash(_('终身支付链接创建失败，请稍后再试'))
    return redirect('/vip')

# PayPal支付成功回调（自动开通会员）
# 月度会员支付成功回调
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
        user.vip_expire = datetime.utcnow() + timedelta(days=30)  # 30天有效期
        new_payment = Payment(
            user_id=user.id,
            plan="month",
            amount=4.99,
            is_success=True
        )
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', 
                              vip_expire=user.vip_expire.strftime('%Y-%m-%d'),
                              plan="月度会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')

# 年度会员支付成功回调
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
        user.vip_expire = datetime.utcnow() + timedelta(days=365)  # 365天有效期
        new_payment = Payment(
            user_id=user.id,
            plan="annual",
            amount=47.88,
            is_success=True
        )
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', 
                              vip_expire=user.vip_expire.strftime('%Y-%m-%d'),
                              plan="年度会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')

# 终身会员支付成功回调
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
        user.vip_expire = datetime.utcnow() + timedelta(days=9999)  # 终身有效期
        new_payment = Payment(
            user_id=user.id,
            plan="lifetime",
            amount=199.00,
            is_success=True
        )
        db.session.add(new_payment)
        db.session.commit()
        return redirect(url_for('success', 
                              vip_expire=user.vip_expire.strftime('%Y-%m-%d'),
                              plan="终身会员"))
    else:
        flash(_('支付验证失败，请联系管理员'))
        return redirect('/vip')


# ------------------- 在这里添加第3步的success路由 -------------------
@app.route('/success')
def success():
    vip_expire = request.args.get('vip_expire', '未知')
    plan = request.args.get('plan', '会员')  # 接收会员类型
    return render_template('success.html', vip_expire=vip_expire, plan=plan)
# -------------------------------------------------------------------


@app.route('/history')
@login_required
def history():
    if not current_user.is_vip:
        return redirect('/vip')
    histories = History.query.filter_by(user_id=current_user.id).order_by(History.handle_time.desc()).all()
    return render_template('history.html', histories=histories)


# ------------------- 修改后的代码开始 -------------------
@app.route('/invite')
@login_required
def invite():
    # 查询当前用户邀请的所有用户（通过inviter_id关联）
    invited_users = User.query.filter_by(inviter_id=current_user.id).all()
    # 传递邀请码和邀请人数到模板
    return render_template(
        'invite.html', 
        invite_code=current_user.invite_code,
        invited_count=len(invited_users)  # 邀请成功的人数
    )
# ------------------- 修改后的代码结束 -------------------

@app.route('/set-lang')
def set_lang():
    lang = request.args.get('lang', 'zh')
    response = make_response(redirect(request.referrer or '/'))
    response.set_cookie('lang', lang, max_age=30*24*3600)
    return response
# 底部4个页面的路由（添加到app.py中）
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')  # 对应隐私政策页面

@app.route('/terms')
def terms():
    return render_template('terms.html')    # 对应服务条款页面

@app.route('/about')
def about():
    return render_template('about.html')    # 对应关于我们页面

@app.route('/contact')
def contact():
    return render_template('contact.html')  # 对应联系我们页面


@app.route('/pay/callback', methods=['POST'])
def pay_callback():
    # 替换为你的支付平台回调逻辑（示例）
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


# 初始化数据库
with app.app_context():
    print("开始创建表结构...")  # 新增日志
    db.create_all()
    print("表结构创建完成！")  # 新增日志


if __name__ == '__main__':
    app.run(debug=True, port=5001)