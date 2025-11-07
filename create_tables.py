from app import app, db  # 导入你的Flask应用和数据库实例

with app.app_context():
    db.create_all()  # 创建所有模型对应的表结构
    print("MySQL表结构创建成功！")