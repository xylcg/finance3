import os
from dotenv import load_dotenv

# 基础目录设置
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()  # 加载.env文件中的环境变量

class Config:
    # 安全密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-123'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'finance.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 邮件服务器配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@financeapp.com')
    
    # 分页设置
    ITEMS_PER_PAGE = 10
    
    # 提醒设置
    BUDGET_ALERT_DAYS = 3  # 预算提醒提前天数
    GOAL_REMINDER_DAYS = 7  # 目标提醒提前天数
    
    # 文件上传设置
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # 应用名称
    APP_NAME = "个人财务管理系统"
    
    # 分类选项
    CATEGORIES = [
        '餐饮', '购物', '交通', '娱乐', 
        '住房', '医疗', '教育', '投资',
        '工资', '奖金', '其他收入', '其他支出'
    ]
    
    # 预算周期选项
    BUDGET_PERIODS = ['月度', '季度', '年度']