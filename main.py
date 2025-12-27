from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from datetime import datetime

app = Flask(__name__)


# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'supermarket_admin',
    'password': 'admin123',
    'database': 'Supermarket'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)


@app.route('/')
def shop_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all products and categories for the store front
    cursor.execute(
        "SELECT P.*, C.Name as CategoryName FROM Products P LEFT JOIN Categories C ON P.CategoryID = C.CategoryID")
    products = cursor.fetchall()

    # Get customers so we can "simulate" who is shopping
    cursor.execute("SELECT CustomerID, FirstName, LastName FROM Customers")
    customers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('shop.html', products=products, customers=customers)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    customer_id = request.form.get('customer_id')
    product_id = request.form.get('product_id')

    if not customer_id:
        return "Error: Please select a customer at the top of the page.", 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if item is already in cart to update quantity, otherwise insert new
    query = """
            INSERT INTO Carts (CustomerID, ProductID, Quantity)
            VALUES (%s, %s, 1) ON DUPLICATE KEY \
            UPDATE Quantity = Quantity + 1 \
            """
    cursor.execute(query, (customer_id, product_id))
    conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for('view_cart', customer_id=customer_id))


@app.route('/cart/<int:customer_id>')
def view_cart(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch cart items with product details
    query = """
            SELECT P.Name, P.UnitPrice, P.Discount, C.Quantity, P.ProductID
            FROM Carts C
                     JOIN Products P ON C.ProductID = P.ProductID
            WHERE C.CustomerID = %s \
            """
    cursor.execute(query, (customer_id,))
    items = cursor.fetchall()

    # Calculate total using price minus discount
    total = sum(((item['UnitPrice'] - item['Discount']) * item['Quantity']) for item in items)

    cursor.close()
    conn.close()
    return render_template('cart.html', items=items, total=total, customer_id=customer_id)


@app.route('/checkout/<int:customer_id>', methods=['POST'])
def checkout(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Get current cart items
    cursor.execute(
        "SELECT C.*, P.UnitPrice, P.Discount FROM Carts C JOIN Products P ON C.ProductID = P.ProductID WHERE CustomerID = %s",
        (customer_id,))
    cart_items = cursor.fetchall()

    if not cart_items:
        return redirect(url_for('shop_page'))

    # 2. Calculate Total Amount
    total_amount = sum(((item['UnitPrice'] - item['Discount']) * item['Quantity']) for item in cart_items)

    # 3. Create a Transaction record (defaulting to EmployeeID 1 as the processor)
    # The database requires EmployeeID [cite: 52]
    cursor.execute("""
                   INSERT INTO Transactions (TransactionTimestamp, TotalAmount, CustomerID, EmployeeID)
                   VALUES (%s, %s, %s, %s)
                   """, (datetime.now(), total_amount, customer_id, 1))
    transaction_id = cursor.lastrowid

    # 4. Move items to TransactionItems (Historical record)
    for item in cart_items:
        price_paid = item['UnitPrice'] - item['Discount']
        cursor.execute("""
                       INSERT INTO TransactionItems (TransactionID, ProductID, Quantity, PriceAtTimeOfSale)
                       VALUES (%s, %s, %s, %s)
                       """, (transaction_id, item['ProductID'], item['Quantity'], price_paid))

    # 5. Clear the cart
    cursor.execute("DELETE FROM Carts WHERE CustomerID = %s", (customer_id,))

    conn.commit()
    cursor.close()
    conn.close()
    return "Purchase Successful! <a href='/shop'>Return to Shop</a>"

@app.route('/admin')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT CustomerID,FirstName,LastName,Phone,Address FROM Customers")
    customer = cursor.fetchall()

    cursor.execute("SELECT ProductID,Name,UnitPrice,Discount FROM products")
    products = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('dashboard.html',customer=customer,products=products)

########################################################################################################################
########################################    Customer      ##############################################################
########################################################################################################################
@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO Customers (FirstName, LastName, Email, Password, Phone, Address)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (first_name, last_name, email, password, phone, address)

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('dashboard'))

    return render_template('add_customer.html')

@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name  = request.form['last_name']
        email      = request.form['email']
        password   = request.form['password']
        phone      = request.form['phone']
        address    = request.form['address']

        cursor2 = conn.cursor()
        query = """
            UPDATE Customers
            SET FirstName=%s, LastName=%s, Email=%s, Password=%s, Phone=%s, Address=%s
            WHERE CustomerID=%s
        """
        values = (first_name, last_name, email, password, phone, address, customer_id)
        cursor2.execute(query, values)
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM Customers WHERE CustomerID = %s", (customer_id,))
    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('edit_customer.html', customer=customer)


@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM Customers WHERE CustomerID = %s", (customer_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('dashboard'))

########################################################################################################################
########################################    product      ###############################################################
########################################################################################################################
@app.route('/products')
def products_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT P.ProductID, P.Name, P.UnitPrice, P.Discount, C.Name AS CategoryName, P.CategoryID
        FROM Products P
        LEFT JOIN Categories C ON P.CategoryID = C.CategoryID
        ORDER BY P.ProductID DESC
    """)
    products = cursor.fetchall()

    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('products.html', products=products, categories=categories)


@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    unit_price = request.form['unit_price']
    discount = request.form.get('discount', 0) or 0
    category_id = request.form.get('category_id') or None

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Products (Name, UnitPrice, Discount, CategoryID)
        VALUES (%s, %s, %s, %s)
    """, (name, unit_price, discount, category_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('products_page'))


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        unit_price = request.form['unit_price']
        discount = request.form.get('discount', 0) or 0
        category_id = request.form.get('category_id') or None

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE Products
            SET Name=%s, UnitPrice=%s, Discount=%s, CategoryID=%s
            WHERE ProductID=%s
        """, (name, unit_price, discount, category_id, product_id))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('products_page'))

    cursor.execute("SELECT * FROM Products WHERE ProductID=%s", (product_id,))
    product = cursor.fetchone()

    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('edit_product.html', product=product, categories=categories)


@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Products WHERE ProductID=%s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('products_page'))

if __name__ == '__main__':
    app.run(debug=True)