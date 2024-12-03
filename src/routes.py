from flask import Flask, request, jsonify, make_response
from src import app, db
from src.models import User, Products, Cart

def is_authenticated():
    username = request.cookies.get('email')
    print(request.cookies)
    if username:
        user = User.query.filter_by(email=username).first()
        if user:
            return True, user

@app.route("/")
def home():
    if is_authenticated():
        return jsonify({"message": f"Hello,{request.cookies.get('email')}"})
        
    return jsonify({"message": f"Not authenticated"}), 403

@app.route("/register", methods=['POST'])
def register():
    data = request.json
    if not data or not all(k in data for k in ("lastname", "firstname", "email", "password")):
        return jsonify({"error": "Missing required fields"}), 400

    user = User(
        lastname=data["lastname"],
        firstname=data["firstname"],
        email=data["email"],
        password=data['password'],
        user_type='consumer'
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created successfully"}), 201

@app.route("/admin/load", methods=['GET'])
def load_admin():
    
    if not User.query.filter_by(email="admin@test.com"):
        user = User(
            lastname='test',
            firstname='admin',
            email='admin@test.com',
            password='password',
            user_type='admin'
        )
        db.session.add(user)
        db.session.commit()
    return jsonify({"email":"admin@test.com", "password": "password"}), 201

@app.route("/login", methods=['POST'])
def login():
    data = request.json
    if not data or not all(k in data for k in ("email", "password")):
        return jsonify({"error": "Missing required fields"}), 400

    user = User.query.filter_by(email=data["email"], password=data["password"]).first()
    if user:
        response = make_response(jsonify({"message": "Login successful"}))
        response.set_cookie("email", user.email, httponly=True)
        return response

    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Logged out successfully"}))
    response.delete_cookie("username")
    return response

@app.route("/account", methods=["GET", "PUT"])
def account():
    authenticated, user = is_authenticated()
    if not authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "GET":
        return jsonify({
            "lastname": user.lastname,
            "firstname": user.firstname,
            "email": user.email,
            "noOfItems": Cart.query.filter_by(user_id=user.id).count(),
        })

    # Update account
    data = request.json
    if "lastname" in data:
        user.lastname = data["lastname"]
    if "firstname" in data:
        user.firstname = data["firstname"]
    if "email" in data:
        user.email = data["email"]
    db.session.commit()
    return jsonify({"message": "Account updated successfully"})

@app.route("/products", methods=["GET"])
def products():
    authenticated, _ = is_authenticated()
    if authenticated:
        products = Products.query.all()
        products_list = [
            {"id": p.id, "name": p.name, "price": p.price}
            for p in products
        ]
        return jsonify({"products": products_list})
    return jsonify({"message": "Please login"})



@app.route('/admin/products', methods=['POST'])
def create_product():
    data = request.get_json()
    new_product = Products(
        name=data['name'],
        price=data['price'],
        description=data['description'],
        stock=data['stock']
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify({'message': 'Product created', 'product': new_product.id}), 201

# Retrieve a single product by ID
@app.route('/admin/products/<int:id>', methods=['GET'])
def get_product(id):
    product = Products.query.get_or_404(id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'description': product.description,
        'stock': product.stock
    })

# List all products
@app.route('/admin/products', methods=['GET'])
def list_products():
    products = Products.query.all()
    products_list = [
        {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'description': product.description,
            'stock': product.stock
        }
        for product in products
    ]
    return jsonify(products_list)

# Update an existing product
@app.route('/admin/products/<int:id>', methods=['PUT'])
def update_product(id):
    product = Products.query.get_or_404(id)
    data = request.get_json()
    product.name = data.get('name', product.name)
    product.price = data.get('price', product.price)
    product.description = data.get('description', product.description)
    product.stock = data.get('stock', product.stock)
    db.session.commit()
    return jsonify({'message': 'Product updated'})

# Delete a product
@app.route('/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = Products.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': 'Product deleted'})


@app.route("/cart", methods=["GET", "POST", "DELETE"])
def cart():
    authenticated, user = is_authenticated()
    if authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "GET":
        cart_items = Products.query.join(Cart).add_columns(
            Cart.quantity, Products.price, Products.name, Products.id
        ).filter_by(buyer=user).all()

        cart_list = [
            {
                "product_id": item.id,
                "name": item.name,
                "price": item.price,
                "quantity": cart.quantity,
            }
            for item, cart in cart_items
        ]
        subtotal = sum(item.price * cart.quantity for item, cart in cart_items)
        return jsonify({"cart": cart_list, "subtotal": subtotal})

    if request.method == "POST":
        data = request.json
        if not data or "product_id" not in data:
            return jsonify({"error": "Missing product_id"}), 400

        product_id = data["product_id"]
        cart_item = Cart.query.filter_by(product_id=product_id, buyer=user).first()
        if cart_item:
            cart_item.quantity += 1
        else:
            new_cart_item = Cart(product_id=product_id, buyer=user, quantity=1)
            db.session.add(new_cart_item)
        db.session.commit()
        return jsonify({"message": "Item added to cart"}), 201

    if request.method == "DELETE":
        data = request.json
        if not data or "product_id" not in data:
            return jsonify({"error": "Missing product_id"}), 400

        cart_item = Cart.query.filter_by(product_id=data["product_id"], buyer=user).first()
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
            return jsonify({"message": "Item removed from cart"}), 200
        return jsonify({"error": "Item not found in cart"}), 404

