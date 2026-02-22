import json
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my-shop-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- Site settings persistence (instance/settings.json) -------------------------------------------------
SETTINGS_PATH = os.path.join(app.instance_path, 'settings.json')


def load_site_settings():
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        if not os.path.exists(SETTINGS_PATH):
            # default settings
            default = {
                'hero_image': 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1600&q=80',
                'hero_overlay': 'rgba(24, 16, 12, 0.42)'
            }
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default

        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'hero_image': 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1600&q=80',
            'hero_overlay': 'rgba(24, 16, 12, 0.42)'
        }


def save_site_settings(settings: dict):
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# -------------------------------------------------------------------------------------------------------


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False, default='Electronics')
    rating = db.Column(db.Float, nullable=False, default=4.5)
    review_text = db.Column(db.Text, nullable=True)
    is_new = db.Column(db.Boolean, nullable=False, default=False)
    is_sale = db.Column(db.Boolean, nullable=False, default=False)
    stock = db.Column(db.Integer, nullable=False, default=0)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False, default='PromptPay QR')
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='orders')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)

    order = db.relationship('Order', backref='items')
    product = db.relationship('Product')


def migrate_schema_for_existing_db():
    table_info = db.session.execute(db.text('PRAGMA table_info(product)')).all()
    if not table_info:
        return

    existing_columns = {row[1] for row in table_info}
    alter_map = {
        'description': "ALTER TABLE product ADD COLUMN description TEXT",
        'category': "ALTER TABLE product ADD COLUMN category VARCHAR(50) DEFAULT 'Electronics' NOT NULL",
        'rating': "ALTER TABLE product ADD COLUMN rating FLOAT DEFAULT 4.5 NOT NULL",
        'review_text': "ALTER TABLE product ADD COLUMN review_text TEXT",
        'is_new': "ALTER TABLE product ADD COLUMN is_new BOOLEAN DEFAULT 0 NOT NULL",
        'is_sale': "ALTER TABLE product ADD COLUMN is_sale BOOLEAN DEFAULT 0 NOT NULL",
        'stock': "ALTER TABLE product ADD COLUMN stock INTEGER DEFAULT 0 NOT NULL",
    }

    for column_name, sql_statement in alter_map.items():
        if column_name not in existing_columns:
            db.session.execute(db.text(sql_statement))

    order_table_info = db.session.execute(db.text('PRAGMA table_info("order")')).all()
    if order_table_info:
        order_columns = {row[1] for row in order_table_info}
        if 'status' not in order_columns:
            db.session.execute(db.text("ALTER TABLE \"order\" ADD COLUMN status VARCHAR(20) DEFAULT 'pending' NOT NULL"))

    db.session.commit()


def seed_products():
    if Product.query.count() > 0:
        return

    sample_products = [
        Product(
            name='Smart Watch',
            price=1990.0,
            image_url='https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=800&q=80',
            description='นาฬิกาอัจฉริยะสำหรับสายสุขภาพ พร้อมแจ้งเตือนครบ',
            category='Watch',
            rating=4.7,
            review_text='แบตอึดมาก ใส่สบาย ใช้งานง่าย',
            is_new=True,
            is_sale=True,
            stock=40,
        ),
        Product(
            name='Headphones',
            price=1490.0,
            image_url='https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=800&q=80',
            description='หูฟังเสียงคมชัด เบสแน่น ตัดเสียงรบกวนได้ดี',
            category='Electronics',
            rating=4.5,
            review_text='เสียงดีมาก คุ้มราคาสุดๆ',
            is_new=False,
            is_sale=False,
            stock=25,
        ),
        Product(
            name='Backpack',
            price=890.0,
            image_url='https://images.unsplash.com/photo-1585386959984-a4155224a1ad?auto=format&fit=crop&w=800&q=80',
            description='กระเป๋าแฟชั่นใส่ของได้เยอะ เหมาะกับทุกวัน',
            category='Fashion',
            rating=4.4,
            review_text='ใส่ของได้เยอะ วัสดุดีเกินราคา',
            is_new=False,
            is_sale=True,
            stock=18,
        ),
        Product(
            name='Sneakers',
            price=1290.0,
            image_url='https://images.unsplash.com/photo-1580910051074-3eb694886505?auto=format&fit=crop&w=800&q=80',
            description='รองเท้าผ้าใบสวมสบาย แมทช์ง่ายทุกลุค',
            category='Fashion',
            rating=4.6,
            review_text='ทรงสวย ใส่เดินทั้งวันไม่เมื่อย',
            is_new=True,
            is_sale=False,
            stock=30,
        ),
    ]

    db.session.add_all(sample_products)
    db.session.commit()


with app.app_context():
    db.create_all()
    migrate_schema_for_existing_db()
    seed_products()
    # ensure site settings file exists at startup
    try:
        load_site_settings()
    except Exception:
        # best-effort only; failures will be surfaced when saving via admin
        pass


def save_uploaded_image(file_storage):
    """Save uploaded FileStorage into static/images and return the URL path or None."""
    if not file_storage:
        return None

    filename = secure_filename(file_storage.filename or '')
    if not filename:
        return None

    images_dir = os.path.join(app.root_path, 'static', 'images')
    os.makedirs(images_dir, exist_ok=True)

    name, ext = os.path.splitext(filename)
    timestamp = int(time.time() * 1000)
    safe_name = f"{name}_{timestamp}{ext}"
    dest_path = os.path.join(images_dir, safe_name)
    file_storage.save(dest_path)
    return f'/static/images/{safe_name}'


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)

    return wrapped_view


def user_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('user_id'):
            flash('กรุณาเข้าสู่ระบบก่อนทำรายการสั่งซื้อ')
            return redirect(url_for('user_login', next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_user_context():
    return {
        'current_user_name': session.get('user_name'),
        'is_admin': session.get('is_admin', False),
    }


@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', 'All').strip()
    products_query = Product.query
    if search:
        products_query = products_query.filter(Product.name.ilike(f'%{search}%'))
    if category and category != 'All':
        # Product.category may contain comma-separated categories; match any that contains the chosen category
        products_query = products_query.filter(Product.category.ilike(f'%{category}%'))

    products = products_query.order_by(Product.id.desc()).all()

    # Build dynamic categories list from stored product categories
    all_products = Product.query.with_entities(Product.category).all()
    category_set = set()
    for (cat_str,) in all_products:
        if not cat_str:
            continue
        for part in cat_str.split(','):
            part = part.strip()
            if part:
                category_set.add(part)

    categories = ['All'] + sorted(category_set)
    site_settings = load_site_settings()
    return render_template(
        'index.html',
        products=products,
        categories=categories,
        selected_category=category,
        search_text=search,
        site_settings=site_settings,
    )


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)


@app.route('/cart')
def cart():
    products = Product.query.all()
    return render_template('cart.html', products=products)


@app.route('/checkout', methods=['GET', 'POST'])
@user_required
def checkout():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        payment_method = request.form.get('payment_method', 'PromptPay QR').strip()
        cart_payload = request.form.get('cart_payload', '').strip()

        if not customer_name or not address or not phone:
            flash('กรุณากรอกข้อมูลให้ครบ')
            return redirect(url_for('checkout'))

        try:
            items = json.loads(cart_payload)
        except json.JSONDecodeError:
            items = []

        if not items:
            flash('ตะกร้าสินค้าว่าง ไม่สามารถสั่งซื้อได้')
            return redirect(url_for('cart'))

        product_ids = [item.get('id') for item in items if item.get('id')]
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        product_map = {product.id: product for product in products}

        order_items = []
        total_price = 0.0
        for item in items:
            product_id = item.get('id')
            quantity = int(item.get('qty', 0))
            product = product_map.get(product_id)
            if not product or quantity <= 0:
                continue

            total_price += product.price * quantity
            order_items.append((product, quantity))

        if not order_items:
            flash('ไม่พบรายการสินค้าที่ถูกต้อง')
            return redirect(url_for('cart'))

        order = Order(
            user_id=session['user_id'],
            customer_name=customer_name,
            address=address,
            phone=phone,
            payment_method=payment_method,
            total_price=total_price,
        )
        db.session.add(order)
        db.session.flush()

        for product, quantity in order_items:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.price,
                )
            )

        db.session.commit()
        flash(f'ยืนยันคำสั่งซื้อเรียบร้อยแล้ว (Order #{order.id})')
        return redirect(url_for('checkout_success', order_id=order.id))

    products = Product.query.all()
    return render_template('checkout.html', products=products)


@app.route('/checkout/success/<int:order_id>')
@user_required
def checkout_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != session.get('user_id') and not session.get('is_admin'):
        return redirect(url_for('index'))
    return render_template('checkout_success.html', order=order)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()

        if not full_name or not username or not password:
            flash('กรุณากรอกข้อมูลสมัครสมาชิกให้ครบ')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username นี้ถูกใช้แล้ว')
            return redirect(url_for('register'))

        user = User(
            full_name=full_name,
            username=username,
            password_hash=generate_password_hash(password),
            phone=phone,
        )
        db.session.add(user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ')
        return redirect(url_for('user_login'))

    return render_template('register.html')


@app.route('/user-login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('เข้าสู่ระบบไม่สำเร็จ')
            return redirect(url_for('user_login'))

        session['user_id'] = user.id
        session['user_name'] = user.full_name
        next_url = request.args.get('next')
        return redirect(next_url or url_for('index'))

    return render_template('user_login.html')


@app.route('/customer-login', methods=['GET', 'POST'])
def customer_login_alias():
    return user_login()


@app.route('/user-logout')
def user_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username == 'admin' and password == '1234':
            session['is_admin'] = True
            return redirect(url_for('admin'))

        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')

    return render_template('login.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login_alias():
    return login()


@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def admin():
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_orders = Order.query.count()
    total_sales = db.session.query(db.func.coalesce(db.func.sum(Order.total_price), 0)).scalar() or 0
    product_count = Product.query.count()
    user_count = User.query.count()
    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()

    latest_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    selected_section = request.args.get('section', 'dashboard').strip()

    today_text = datetime.utcnow().date().isoformat()
    today_orders = Order.query.filter(db.func.date(Order.created_at) == today_text).count()
    today_sales = (
        db.session.query(db.func.coalesce(db.func.sum(Order.total_price), 0))
        .filter(db.func.date(Order.created_at) == today_text)
        .scalar()
        or 0
    )

    return render_template(
        'admin.html',
        total_orders=total_orders,
        total_sales=total_sales,
        product_count=product_count,
        user_count=user_count,
        today_orders=today_orders,
        today_sales=today_sales,
        latest_orders=latest_orders,
        products=products,
        orders=orders,
        users=users,
        selected_section=selected_section,
    )


@app.route('/admin/products')
@admin_required
def admin_products():
    return redirect(url_for('admin_dashboard', section='products'))


@app.route('/admin/products/new', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_text = request.form.get('price', '').strip()
        image_url = request.form.get('image_url', '').strip()
        # handle uploaded image file (optional)
        uploaded = request.files.get('image_file')
        if uploaded and getattr(uploaded, 'filename', '').strip():
            saved = save_uploaded_image(uploaded)
            if saved:
                image_url = saved
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Electronics').strip()
        rating_text = request.form.get('rating', '4.5').strip()
        review_text = request.form.get('review_text', '').strip()
        stock_text = request.form.get('stock', '0').strip()
        is_new = bool(request.form.get('is_new'))
        is_sale = bool(request.form.get('is_sale'))

        if not name or not price_text:
            flash('กรุณากรอกชื่อสินค้าและราคาให้ครบ')
            return redirect(url_for('add_product'))

        try:
            price = float(price_text)
            rating = float(rating_text)
            stock = int(stock_text)
        except ValueError:
            flash('ราคา/เรตติ้ง/สต็อกไม่ถูกต้อง')
            return redirect(url_for('add_product'))

        # Normalize categories: split, strip, remove duplicates, rejoin with comma
        cats = [c.strip() for c in category.split(',') if c.strip()]
        category_norm = ', '.join(dict.fromkeys(cats)) if cats else 'Electronics'

        new_product = Product(
            name=name,
            price=price,
            image_url=image_url,
            description=description,
            category=category_norm,
            rating=rating,
            review_text=review_text,
            stock=stock,
            is_new=is_new,
            is_sale=is_sale,
        )
        db.session.add(new_product)
        db.session.commit()
        flash('เพิ่มสินค้าเรียบร้อยแล้ว')
        return redirect(url_for('admin_dashboard', section='products'))

    return render_template('admin_product_form.html', mode='add', product=None)


@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        # allow new uploaded image to replace existing
        product.image_url = request.form.get('image_url', '').strip()
        uploaded = request.files.get('image_file')
        if uploaded and getattr(uploaded, 'filename', '').strip():
            saved = save_uploaded_image(uploaded)
            if saved:
                product.image_url = saved
        product.description = request.form.get('description', '').strip()
        # Accept comma-separated categories and normalize
        raw_cat = request.form.get('category', 'Electronics').strip()
        cats = [c.strip() for c in raw_cat.split(',') if c.strip()]
        product.category = ', '.join(dict.fromkeys(cats)) if cats else 'Electronics'
        product.review_text = request.form.get('review_text', '').strip()
        product.is_new = bool(request.form.get('is_new'))
        product.is_sale = bool(request.form.get('is_sale'))

        try:
            product.price = float(request.form.get('price', product.price))
            product.rating = float(request.form.get('rating', product.rating))
            product.stock = int(request.form.get('stock', product.stock))
        except ValueError:
            flash('ราคา/เรตติ้ง/สต็อกไม่ถูกต้อง')
            return redirect(url_for('edit_product', product_id=product.id))

        db.session.commit()
        flash('แก้ไขสินค้าเรียบร้อยแล้ว')
        return redirect(url_for('admin_dashboard', section='products'))

    return render_template('admin_product_form.html', mode='edit', product=product)


@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('ลบสินค้าเรียบร้อยแล้ว')
    return redirect(url_for('admin_dashboard', section='products'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    return redirect(url_for('admin_dashboard', section='orders'))


@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    next_status = request.form.get('status', '').strip()
    allowed = {'pending', 'shipped', 'cancelled'}
    if next_status not in allowed:
        flash('สถานะไม่ถูกต้อง')
        return redirect(url_for('admin_dashboard', section='orders'))

    order.status = next_status
    db.session.commit()
    flash('อัปเดตสถานะคำสั่งซื้อแล้ว')
    return redirect(url_for('admin_dashboard', section='orders'))


@app.route('/admin/add', methods=['POST'])
@admin_required
def add_product_legacy():
    return add_product()


@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product_legacy(product_id):
    return edit_product(product_id)


@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product_legacy(product_id):
    return delete_product(product_id)


@app.route('/admin/users')
@admin_required
def admin_users():
    return redirect(url_for('admin_dashboard', section='users'))


@app.route('/admin/static-images')
@admin_required
def list_static_images():
    """Return JSON list of image filenames under static/images (safe, filtered by extension)."""
    import os

    images_dir = os.path.join(app.root_path, 'static', 'images')
    allowed_ext = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    images = []
    try:
        for fname in os.listdir(images_dir):
            # only include files with allowed extensions
            _, ext = os.path.splitext(fname)
            if ext.lower() in allowed_ext:
                images.append(fname)
    except FileNotFoundError:
        images = []

    # return URLs relative to server root
    images_urls = [f'/static/images/{fn}' for fn in sorted(images)]
    return jsonify({'images': images_urls})


# Theme upload endpoint removed (feature disabled)


if __name__ == '__main__':
    app.run(debug=True)
