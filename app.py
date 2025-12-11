from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'school-canteen-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///canteen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')
    grade = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    
class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref=db.backref('items', lazy=True))
    available = db.Column(db.Boolean, default=True)
    
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    items = db.Column(db.Text)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    order_date = db.Column(db.DateTime, default=datetime.utcnow)

# Создание таблиц
with app.app_context():
    db.create_all()
    
    if not Category.query.first():
        categories = [
            Category(name='Завтраки', description='Полезные завтраки'),
            Category(name='Основные блюда', description='Горячие обеды'),
            Category(name='Напитки', description='Соки, компоты'),
            Category(name='Выпечка', description='Свежая выпечка'),
        ]
        
        for cat in categories:
            db.session.add(cat)
        
        menu_items = [
            MenuItem(name='Омлет с сыром', description='Омлет с сыром и зеленью', price=120.0, category_id=1),
            MenuItem(name='Каша молочная', description='Овсяная каша с фруктами', price=85.0, category_id=1),
            MenuItem(name='Куриная котлета с пюре', description='Котлета с картофельным пюре', price=150.0, category_id=2),
            MenuItem(name='Компот из сухофруктов', description='Освежающий напиток', price=35.0, category_id=3),
            MenuItem(name='Булочка с маком', description='Свежая булочка', price=40.0, category_id=4),
        ]
        
        for item in menu_items:
            db.session.add(item)
        
        admin_user = User(
            username='admin',
            email='admin@school.ru',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        
        test_student = User(
            username='ivanov',
            email='ivanov@school.ru',
            password=generate_password_hash('password123'),
            role='student',
            grade='10A'
        )
        
        db.session.add(admin_user)
        db.session.add(test_student)
        db.session.commit()

# Главная страница
@app.route('/')
def index():
    categories = Category.query.all()
    featured_items = MenuItem.query.filter_by(available=True).limit(4).all()
    return render_template('index.html', categories=categories, featured_items=featured_items)

# Меню
@app.route('/menu')
def menu():
    categories = Category.query.all()
    items = MenuItem.query.filter_by(available=True).all()
    return render_template('menu.html', items=items, categories=categories)

# Корзина
@app.route('/cart')
def cart():
    cart_items = []
    total = 0
    
    if 'cart' in session:
        cart_data = session.get('cart', {})
        for item_id, quantity in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.available:
                item_total = item.price * quantity
                cart_items.append({
                    'item': item,
                    'quantity': quantity,
                    'total': item_total
                })
                total += item_total
    
    return render_template('cart.html', cart_items=cart_items, total=total)

# Добавление в корзину
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    cart = session.get('cart', {})
    if item_id in cart:
        cart[item_id] += quantity
    else:
        cart[item_id] = quantity
    
    session['cart'] = cart
    return jsonify({'success': True, 'cart_count': sum(cart.values())})

# Оформление заказа
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'cart' not in session or not session['cart']:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        cart_data = session.get('cart', {})
        order_items = []
        total = 0
        
        for item_id, quantity in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item:
                order_items.append({
                    'item_id': item.id,
                    'name': item.name,
                    'price': item.price,
                    'quantity': quantity
                })
                total += item.price * quantity
        
        order = Order(
            user_id=session['user_id'],
            items=json.dumps(order_items),
            total_price=total,
            status='pending'
        )
        
        db.session.add(order)
        db.session.commit()
        
        session.pop('cart', None)
        flash(f'Заказ №{order.id} оформлен!', 'success')
        return redirect(url_for('my_orders'))
    
    return render_template('checkout.html')

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Пользователь уже существует', 'error')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role='student'
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверные данные', 'error')
    
    return render_template('login.html')

# Выход
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли', 'info')
    return redirect(url_for('index'))

# Мои заказы
@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session:
        flash('Войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.order_date.desc()).all()
    for order in orders:
        order.items_list = json.loads(order.items)
    
    return render_template('my_orders.html', orders=orders)

# Админка
@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
    
    orders = Order.query.order_by(Order.order_date.desc()).all()
    for order in orders:
        order.items_list = json.loads(order.items)
    
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/update_order_status', methods=['POST'])
def update_order_status():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False})
    
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    order = Order.query.get(order_id)
    if order:
        order.status = new_status
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False})

# Запуск
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
