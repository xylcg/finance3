from flask import Flask, request, redirect, url_for, flash, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_mail import Mail, Message
from flask_migrate import Migrate
from config import Config
from models import db, User, Transaction, Budget, Goal, Knowledge, user_knowledge
from datetime import datetime, timedelta
from forms import LoginForm, RegistrationForm, TransactionForm, BudgetForm, GoalForm, ProfileForm
from werkzeug.utils import secure_filename
import os
import json
from sqlalchemy import func, extract

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 初始化扩展
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    mail = Mail(app)
    migrate = Migrate(app, db)
    
    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    # 错误处理
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    # 上下文处理器 - 使变量在所有模板中可用
    @app.context_processor
    def inject_vars():
        return dict(
            categories=app.config['CATEGORIES'],
            budget_periods=app.config['BUDGET_PERIODS'],
            app_name=app.config['APP_NAME']
        )
    
    # 辅助函数
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    
    # 认证路由
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash('无效的用户名或密码', 'danger')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        return render_template('auth/login.html', form=form)
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        return render_template('auth/register.html', form=form)
    
    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))
    
    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        form = ProfileForm(obj=current_user)
        if form.validate_on_submit():
            current_user.username = form.username.data
            current_user.email = form.email.data
            
            # 处理头像上传
            if form.avatar.data:
                file = form.avatar.data
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    current_user.avatar = filename
            
            db.session.commit()
            flash('个人资料已更新', 'success')
            return redirect(url_for('profile'))
        return render_template('auth/profile.html', form=form)
    
    # 主路由
    @app.route('/')
    @login_required
    def index():
        # 最近交易
        recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
            .order_by(Transaction.date.desc()).limit(5).all()
        
        # 预算摘要
        active_budgets = Budget.query.filter(
            Budget.user_id == current_user.id,
            Budget.start_date <= datetime.utcnow(),
            Budget.end_date >= datetime.utcnow()
        ).all()
        
        # 目标进度
        active_goals = Goal.query.filter(
            Goal.user_id == current_user.id,
            Goal.target_date >= datetime.utcnow()
        ).all()
        
        # 推荐理财知识
        recommended_knowledge = Knowledge.query.order_by(func.random()).limit(3).all()
        
        return render_template('index.html',
                             recent_transactions=recent_transactions,
                             active_budgets=active_budgets,
                             active_goals=active_goals,
                             recommended_knowledge=recommended_knowledge)
    
    # 交易路由
    @app.route('/transactions')
    @login_required
    def transactions():
        page = request.args.get('page', 1, type=int)
        type_filter = request.args.get('type')
        category_filter = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = Transaction.query.filter_by(user_id=current_user.id)
        
        # 应用过滤器
        if type_filter:
            query = query.filter_by(type=type_filter)
        if category_filter:
            query = query.filter_by(category=category_filter)
        if start_date:
            query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        
        transactions = query.order_by(Transaction.date.desc())\
            .paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
        
        return render_template('transactions/list.html', transactions=transactions)
    
    @app.route('/transactions/add', methods=['GET', 'POST'])
    @login_required
    def add_transaction():
        form = TransactionForm()
        form.goal.choices = [(g.id, g.name) for g in Goal.query.filter_by(user_id=current_user.id).all()]
        
        if form.validate_on_submit():
            transaction = Transaction(
                amount=form.amount.data,
                description=form.description.data,
                type=form.type.data,
                category=form.category.data,
                date=datetime.strptime(form.date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(transaction)
            
            # 更新目标进度
            if form.goal.data:
                goal = Goal.query.get(form.goal.data)
                if goal and goal.user_id == current_user.id:
                    if form.type.data == 'income':
                        goal.current_amount += form.amount.data
                    else:
                        goal.current_amount -= form.amount.data
                    db.session.add(goal)
            
            db.session.commit()
            flash('交易已添加', 'success')
            return redirect(url_for('transactions'))
        return render_template('transactions/add_edit.html', form=form, title='添加交易')
    
    @app.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_transaction(id):
        transaction = Transaction.query.get_or_404(id)
        if transaction.user_id != current_user.id:
            abort(403)
            
        form = TransactionForm(obj=transaction)
        form.goal.choices = [(g.id, g.name) for g in Goal.query.filter_by(user_id=current_user.id).all()]
        
        if form.validate_on_submit():
            transaction.amount = form.amount.data
            transaction.description = form.description.data
            transaction.type = form.type.data
            transaction.category = form.category.data
            transaction.date = datetime.strptime(form.date.data, '%Y-%m-%d')
            
            # 这里可以添加目标更新逻辑
            
            db.session.commit()
            flash('交易已更新', 'success')
            return redirect(url_for('transactions'))
        return render_template('transactions/add_edit.html', form=form, title='编辑交易')
    
    @app.route('/transactions/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_transaction(id):
        transaction = Transaction.query.get_or_404(id)
        if transaction.user_id != current_user.id:
            abort(403)
            
        db.session.delete(transaction)
        db.session.commit()
        flash('交易已删除', 'success')
        return redirect(url_for('transactions'))
    
    # 预算路由
    @app.route('/budgets')
    @login_required
    def budgets():
        budgets = Budget.query.filter_by(user_id=current_user.id)\
            .order_by(Budget.start_date.desc()).all()
        return render_template('budgets/list.html', budgets=budgets)
    
    @app.route('/budgets/add', methods=['GET', 'POST'])
    @login_required
    def add_budget():
        form = BudgetForm()
        if form.validate_on_submit():
            budget = Budget(
                name=form.name.data,
                amount=form.amount.data,
                category=form.category.data,
                period=form.period.data,
                start_date=datetime.strptime(form.start_date.data, '%Y-%m-%d'),
                end_date=datetime.strptime(form.end_date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(budget)
            db.session.commit()
            flash('预算已添加', 'success')
            return redirect(url_for('budgets'))
        return render_template('budgets/add_edit.html', form=form, title='添加预算')
    
    # 目标路由
    @app.route('/goals')
    @login_required
    def goals():
        goals = Goal.query.filter_by(user_id=current_user.id)\
            .order_by(Goal.target_date.asc()).all()
        return render_template('goals/list.html', goals=goals)
    
    @app.route('/goals/add', methods=['GET', 'POST'])
    @login_required
    def add_goal():
        form = GoalForm()
        if form.validate_on_submit():
            goal = Goal(
                name=form.name.data,
                target_amount=form.target_amount.data,
                current_amount=form.current_amount.data,
                target_date=datetime.strptime(form.target_date.data, '%Y-%m-%d'),
                user_id=current_user.id
            )
            db.session.add(goal)
            db.session.commit()
            flash('目标已添加', 'success')
            return redirect(url_for('goals'))
        return render_template('goals/add_edit.html', form=form, title='添加目标')
    
    # 理财知识路由
    @app.route('/knowledge')
    @login_required
    def knowledge():
        page = request.args.get('page', 1, type=int)
        category_filter = request.args.get('category')
        
        query = Knowledge.query
        if category_filter:
            query = query.filter_by(category=category_filter)
            
        knowledge = query.order_by(Knowledge.created_at.desc())\
            .paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
        
        return render_template('knowledge/list.html', knowledge=knowledge)
    
    @app.route('/knowledge/<int:id>')
    @login_required
    def view_knowledge(id):
        item = Knowledge.query.get_or_404(id)
        is_favorite = db.session.query(user_knowledge)\
            .filter_by(user_id=current_user.id, knowledge_id=id)\
            .first() is not None
        return render_template('knowledge/view.html', item=item, is_favorite=is_favorite)
    
    @app.route('/knowledge/<int:id>/favorite', methods=['POST'])
    @login_required
    def favorite_knowledge(id):
        item = Knowledge.query.get_or_404(id)
        if db.session.query(user_knowledge)\
           .filter_by(user_id=current_user.id, knowledge_id=id)\
           .first() is None:
            current_user.favorites.append(item)
            db.session.commit()
            flash('已收藏', 'success')
        else:
            flash('已经收藏过了', 'info')
        return redirect(url_for('view_knowledge', id=id))
    
    # 统计路由
    @app.route('/reports')
    @login_required
    def reports():
        return render_template('reports/index.html')
    
    @app.route('/reports/data')
    @login_required
    def reports_data():
        # 按分类统计支出
        expense_by_category = db.session.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense'
        ).group_by(Transaction.category).all()
        
        # 按月统计收支
        monthly_data = db.session.query(
            extract('year', Transaction.date).label('year'),
            extract('month', Transaction.date).label('month'),
            Transaction.type,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == current_user.id
        ).group_by(
            'year', 'month', 'type'
        ).order_by('year', 'month').all()
        
        # 准备图表数据
        categories = [item[0] for item in expense_by_category]
        expense_totals = [float(item[1]) for item in expense_by_category]
        
        # 按月统计数据整理
        months = []
        income_data = []
        expense_data = []
        
        for item in monthly_data:
            month_str = f"{int(item.year)}-{int(item.month):02d}"
            if month_str not in months:
                months.append(month_str)
                income_data.append(0)
                expense_data.append(0)
            
            idx = months.index(month_str)
            if item.type == 'income':
                income_data[idx] = float(item.total)
            else:
                expense_data[idx] = float(item.total)
        
        return jsonify({
            'expense_by_category': {
                'categories': categories,
                'data': expense_totals
            },
            'monthly_data': {
                'months': months,
                'income': income_data,
                'expense': expense_data
            }
        })
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)