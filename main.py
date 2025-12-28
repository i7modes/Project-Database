from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'alsalam_supermarket_secret_key_2025'

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

    # Check if a customer is logged in via session
    customer_id = session.get('customer_id')
    logged_in_user = None
    if customer_id:
        cursor.execute("SELECT FirstName FROM Customers WHERE CustomerID = %s", (customer_id,))
        logged_in_user = cursor.fetchone()

    # Fetch products with Category name alias [cite: 50]
    cursor.execute("""
                   SELECT P.ProductID, P.Name, P.UnitPrice, P.Discount, P.ImageURL, C.Name AS CategoryName
                   FROM Products P
                            LEFT JOIN Categories C ON P.CategoryID = C.CategoryID
                   ORDER BY P.ProductID DESC
                   """)
    products = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('shop.html', products=products, logged_in_user=logged_in_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Check if the user is a Customer
        cursor.execute("SELECT * FROM Customers WHERE Email = %s AND Password = %s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user['CustomerID']
            session['role'] = 'customer'
            session['user_name'] = user['FirstName']
            cursor.close()
            conn.close()
            # Redirect to shop, not a profile page
            return redirect(url_for('shop_page'))

        # 2. Check if the user is an Employee (Admin/Staff)
        cursor.execute("SELECT * FROM Employees WHERE Email = %s AND Password = %s", (email, password))
        employee = cursor.fetchone()

        cursor.close()
        conn.close()

        if employee:
            session['user_id'] = employee['EmployeeID']
            # Store 'Admin' or 'Staff' role to control the settings icon later
            session['role'] = employee['Role']
            session['user_name'] = employee['FirstName']
            # REDIRECT TO SHOP PAGE (Same as customer)
            return redirect(url_for('shop_page'))

        return "Invalid credentials. <a href='/login'>Try again</a>"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('shop_page'))


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))

    customer_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Customer updates their own info
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        address = request.form['address']

        cursor.execute("""
                       UPDATE Customers
                       SET FirstName=%s,
                           LastName=%s,
                           Phone=%s,
                           Address=%s
                       WHERE CustomerID = %s
                       """, (first_name, last_name, phone, address, customer_id))
        conn.commit()
        session['user_name'] = first_name  # Update session name
        return redirect(url_for('shop_page'))

    cursor.execute("SELECT * FROM Customers WHERE CustomerID = %s", (customer_id,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_profile.html', customer=customer)

# Update Add to Cart to use Session instead of form input
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    user_id = session.get('user_id')
    user_role = session.get('role')

    # Redirect guests to login
    if not user_id:
        return redirect(url_for('login'))

    # If an Admin/Staff somehow triggers this, just send them back to the shop
    if user_role in ['Admin', 'Staff']:
        return redirect(url_for('shop_page'))

    product_id = request.form.get('product_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    # Proceed only for Customers
    query = """
            INSERT INTO Carts (CustomerID, ProductID, Quantity)
            VALUES (%s, %s, 1) ON DUPLICATE KEY
            UPDATE Quantity = Quantity + 1
            """
    cursor.execute(query, (user_id, product_id))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_cart', customer_id=user_id))

@app.route('/cart/<int:customer_id>')
def view_cart(customer_id):
    # Verify the logged-in user is viewing their own cart
    if session.get('user_id') != customer_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
            SELECT P.Name, P.UnitPrice, P.Discount, C.Quantity, P.ProductID
            FROM Carts C
                     JOIN Products P ON C.ProductID = P.ProductID
            WHERE C.CustomerID = %s
            """
    cursor.execute(query, (customer_id,))
    items = cursor.fetchall()

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
    return "Purchase Successful! <a href='/'>Return to Shop</a>"

@app.route('/admin')
def admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT ProductID,Name,UnitPrice,Discount FROM products")
    products = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin.html',products=products)

########################################################################################################################
########################################    Customer      ##############################################################
########################################################################################################################
@app.route('/admin_customer', methods=['GET', 'POST'])
def admin_customer():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT CustomerID,FirstName,LastName,Phone,Address FROM Customers")
    customer = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_customer.html', customer=customer)

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

        return redirect(url_for('admin_customer'))

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
        return redirect(url_for('admin_customer'))

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

    return redirect(url_for('admin_customer'))

########################################################################################################################
########################################    Employee      ###############################################################
########################################################################################################################
@app.route('/admin_employee', methods=['GET', 'POST'])
def admin_employee():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT EmployeeID,FirstName,LastName,Email,Phone,Address,Role FROM employees")
    employee = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin_employee.html', Emp=employee)

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        role = request.form['role']

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO employees (FirstName, LastName, Email, Password, Phone, Address, Role)
        VALUES (%s, %s, %s, %s, %s, %s,%s)
        """
        values = (first_name, last_name, email, password, phone, address,role)

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('admin_employee'))

    return render_template('add_employee.html')

@app.route('/edit_employee/<int:emp_id>', methods=['GET', 'POST'])
def edit_employee(emp_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name  = request.form['last_name']
        email      = request.form['email']
        password   = request.form['password']
        phone      = request.form['phone']
        address    = request.form['address']
        role       = request.form['role']

        cursor2 = conn.cursor()
        query = """
            UPDATE employees
            SET FirstName=%s, LastName=%s, Email=%s, Password=%s, Phone=%s, Address=%s, Role=%s
            WHERE EmployeeID=%s
        """
        values = (first_name, last_name, email, password, phone, address,role, emp_id)
        cursor2.execute(query, values)
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_employee'))

    cursor.execute("SELECT * FROM employees WHERE EmployeeID = %s", (emp_id,))
    employee = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('edit_employee.html', Emp=employee)


@app.route('/delete_employee/<int:emp_id>', methods=['POST'])
def delete_employee(emp_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM employees WHERE EmployeeID = %s", (emp_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('admin_employee'))






########################################################################################################################
########################################    product      ###############################################################
########################################################################################################################
@app.route('/admin_product')
def admin_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Note the use of "AS CategoryName" to match the template variable
    cursor.execute("""
        SELECT P.ProductID, P.Name, P.UnitPrice, P.Discount, P.ImageURL, 
               C.Name AS CategoryName, P.CategoryID
        FROM Products P
        LEFT JOIN Categories C ON P.CategoryID = C.CategoryID
        ORDER BY P.ProductID DESC
    """)
    products = cursor.fetchall()

    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_product.html', products=products, categories=categories)


# Updated route to handle the separate fields page
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        unit_price = request.form['unit_price']
        discount = request.form.get('discount', 0) or 0
        category_id = request.form.get('category_id') or None
        image_url = request.form.get('image_url') or 'default_product.png'

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Products (Name, UnitPrice, Discount, CategoryID, ImageURL)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, unit_price, discount, category_id, image_url))
        conn.commit()
        cursor.close()
        conn.close()
        # Redirect back to the management list after saving
        return redirect(url_for('admin_product'))

    # If GET, fetch categories to populate the dropdown on the fields page
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('add_product.html', categories=categories)

    # GET request: Load categories for the dropdown menu
    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('add_product.html', categories=categories)


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        unit_price = request.form['unit_price']
        discount = request.form.get('discount', 0)
        category_id = request.form.get('category_id')
        image_url = request.form.get('image_url') # Capture the URL field

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE Products
            SET Name=%s, UnitPrice=%s, Discount=%s, CategoryID=%s, ImageURL=%s
            WHERE ProductID=%s
        """, (name, unit_price, discount, category_id, image_url, product_id))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_product'))

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
    return redirect(url_for('admin_product'))

########################################################################################################################
########################################    Warehouse      #############################################################
########################################################################################################################
@app.route('/admin_warehouse')
def admin_warehouse():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
                SELECT W.WarehouseID,W.Name,W.Address
                FROM warehouses W
    """)
    warehouse = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_warehouse.html', warehouse=warehouse)

@app.route('/add_warehouse', methods=['GET', 'POST'])
def add_warehouse():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO warehouses (Name , Address)
        VALUES (%s, %s)
        """
        values = (name,address)

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for('admin_warehouse'))

    return render_template('add_warehouse.html')


@app.route('/edit_warehouse/<int:Ware_id>', methods=['GET', 'POST'])
def edit_warehouse(Ware_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE warehouses
            SET Name=%s, Address=%s
            WHERE WarehouseID=%s
        """, (name, address ,Ware_id))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_warehouse'))

    cursor.execute("SELECT * FROM warehouses WHERE WarehouseID=%s", (Ware_id,))
    warehouse = cursor.fetchone()


    cursor.close()
    conn.close()
    return render_template('edit_warehouse.html', warehouse=warehouse)

@app.route('/admin_warehouse_product/<int:Ware_id>', methods=['GET'])
def admin_warehouse_product(Ware_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
            SELECT P.ProductID,P.Name,S.Quantity,S.WarehouseID
            FROM products P , warehousestock S
            Where S.ProductID = P.ProductID AND S.WarehouseID = %s
    """
    cursor.execute(query, (Ware_id,))
    product = cursor.fetchall()


    cursor.close()
    conn.close()
    return render_template('admin_warehouse_product.html', product=product)

@app.route('/edit_warehouse_product/<int:Ware_id>/<int:P_id>', methods=['GET','POST'])
def edit_warehouse_product(Ware_id,P_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        qunatity = request.form['quantity']

        cursor2 = conn.cursor()
        cursor2.execute("""
            UPDATE warehousestock
            SET Quantity=%s
            WHERE WarehouseID=%s AND ProductID=%s
        """, (qunatity, Ware_id ,P_id))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_warehouse_product',Ware_id=Ware_id))

    cursor.execute("SELECT * FROM warehousestock WHERE WarehouseID=%s AND ProductID=%s", (Ware_id,P_id,))
    warehouse = cursor.fetchone()


    cursor.close()
    conn.close()
    return render_template('edit_warehouse_product.html', warehouse=warehouse)


@app.route('/delete_warehouse_product/<int:Ware_id>/<int:P_id>', methods=['POST'])
def delete_warehouse_product(Ware_id,P_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warehousestock WHERE WarehouseID=%s AND ProductID=%s", (Ware_id,P_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_warehouse_product'))

@app.route('/delete_warehouse/<int:Ware_id>', methods=['POST'])
def delete_warehouse(Ware_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warehouses WHERE WarehouseID=%s", (Ware_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_warehouse'))
if __name__ == '__main__':
    app.run(debug=True)