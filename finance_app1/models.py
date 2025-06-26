from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    """用户模型"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(128))  # 头像路径
    
    # 关系定义
    transactions = db.relationship('Transaction', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    goals = db.relationship('Goal', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    favorites = db.relationship('Knowledge', secondary='user_knowledge', backref=db.backref('users', lazy='dynamic'))
    
    def set_password(self, password):
        """设置密码哈希"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

# 用户收藏知识的关联表
user_knowledge = db.Table('user_knowledge',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('knowledge_id', db.Integer, db.ForeignKey('knowledge.id'), primary_key=True)
)

class Transaction(db.Model):
    """交易记录模型"""
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    type = db.Column(db.String(10), nullable=False)  # 收入/支出
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, index=True, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def __repr__(self):
        return f'<Transaction {self.amount} {self.type}>'

class Budget(db.Model):
    """预算模型"""
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))
    period = db.Column(db.String(20), nullable=False)  # 月度/季度/年度
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def spent_amount(self):
        """计算已花费金额"""
        from sqlalchemy import func
        return db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == self.user_id,
            Transaction.type == 'expense',
            Transaction.category == self.category,
            Transaction.date >= self.start_date,
            Transaction.date <= self.end_date
        ).scalar() or 0
    
    def remaining_amount(self):
        """计算剩余金额"""
        return self.amount - self.spent_amount()
    
    def __repr__(self):
        return f'<Budget {self.name} {self.amount}>'

class Goal(db.Model):
    """财务目标模型"""
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0)
    target_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def progress(self):
        """计算目标进度百分比"""
        return (self.current_amount / self.target_amount) * 100 if self.target_amount > 0 else 0
    
    def days_remaining(self):
        """计算剩余天数"""
        return (self.target_date - datetime.utcnow()).days
    
    def __repr__(self):
        return f'<Goal {self.name} {self.progress()}%>'

class Knowledge(db.Model):
    """理财知识模型"""
    __tablename__ = 'knowledge'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image = db.Column(db.String(128))  # 知识图片路径
    
    def __repr__(self):
        return f'<Knowledge {self.title}>'