from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'alsalam_supermarket_secret_key_2025'

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
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

    # Fetch products with Category name alias
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Capturing required attributes: FirstName, LastName, Email, Password
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '') # Optional
        address = request.form.get('address', '') # Optional

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Ensure account uniqueness by checking the email
        cursor.execute("SELECT * FROM Customers WHERE Email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return "Error: This email is already registered. <a href='/register'>Try a different one.</a>"

        # Insert the new customer into the database
        query = """
            INSERT INTO Customers (FirstName, LastName, Email, Password, Phone, Address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (first_name, last_name, email, password, phone, address))
        conn.commit()

        # Automatically log the user in after registration
        new_user_id = cursor.lastrowid
        session['user_id'] = new_user_id
        session['user_name'] = first_name
        session['role'] = 'customer'

        cursor.close()
        conn.close()
        return redirect(url_for('shop_page'))

    return render_template('register.html')


@app.route('/customer_panel')
def customer_panel():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'customer':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Get Stats (Spent & Orders)
    cursor.execute("SELECT SUM(TotalAmount) as total, COUNT(*) as count FROM Transactions WHERE CustomerID = %s", (user_id,))
    stats = cursor.fetchone()
    total_spent = stats['total'] if stats['total'] else 0
    order_count = stats['count']

    # 2. Get Cart Item Count
    cursor.execute("SELECT SUM(Quantity) as cart_total FROM Carts WHERE CustomerID = %s", (user_id,))
    cart_res = cursor.fetchone()
    cart_count = cart_res['cart_total'] if cart_res['cart_total'] else 0

    # 3. Get Transaction History
    cursor.execute("SELECT * FROM Transactions WHERE CustomerID = %s ORDER BY TransactionTimestamp DESC LIMIT 5", (user_id,))
    transactions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('customer_panel.html',
                           total_spent=total_spent,
                           order_count=order_count,
                           cart_count=cart_count,
                           transactions=transactions)

@app.route('/order_details/<int:transaction_id>')
def order_details(transaction_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch Order Metadata and verify ownership
    cursor.execute("""
        SELECT * FROM Transactions 
        WHERE TransactionID = %s AND CustomerID = %s
    """, (transaction_id, user_id))
    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        return "Order not found or access denied.", 403

    # 2. Fetch all products in this specific transaction
    query = """
        SELECT P.Name, TI.Quantity, TI.PriceAtTimeOfSale, 
               (TI.Quantity * TI.PriceAtTimeOfSale) as Subtotal
        FROM TransactionItems TI
        JOIN Products P ON TI.ProductID = P.ProductID
        WHERE TI.TransactionID = %s
    """
    cursor.execute(query, (transaction_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('order_details.html', order=order, items=items)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Update user information
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')

        cursor.execute("""
                       UPDATE Customers
                       SET FirstName = %s,
                           LastName  = %s,
                           Email     = %s,
                           Phone     = %s,
                           Address   = %s
                       WHERE CustomerID = %s
                       """, (first_name, last_name, email, phone, address, user_id))
        conn.commit()
        session['user_name'] = first_name
        return redirect(url_for('customer_panel'))

    # Fetch current data to pre-fill the form
    cursor.execute("SELECT * FROM Customers WHERE CustomerID = %s", (user_id,))
    user_data = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user_data)

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


@app.route('/delete_from_cart/<int:product_id>', methods=['POST'])
def delete_from_cart(product_id):
    # Verify the user is logged in
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete the specific product for this specific customer
    cursor.execute("""
                   DELETE
                   FROM Carts
                   WHERE CustomerID = %s
                     AND ProductID = %s
                   """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    # Redirect back to the cart page to show the updated list
    return redirect(url_for('view_cart', customer_id=user_id))


@app.route('/update_cart', methods=['POST'])
def update_cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all product IDs and quantities from the form
    # The form will send data like {'qty_1': '5', 'qty_2': '3'}
    for key, value in request.form.items():
        if key.startswith('qty_'):
            product_id = key.split('_')[1]
            try:
                quantity = int(value)
                if quantity > 0:
                    cursor.execute("""
                        UPDATE Carts SET Quantity = %s 
                        WHERE CustomerID = %s AND ProductID = %s
                    """, (quantity, user_id, product_id))
                else:
                    # If quantity is 0, remove it
                    cursor.execute("DELETE FROM Carts WHERE CustomerID = %s AND ProductID = %s", (user_id, product_id))
            except ValueError:
                continue

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


from datetime import datetime


@app.route('/checkout/<int:customer_id>', methods=['POST'])
def checkout(customer_id):
    if session.get('user_id') != customer_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Get current cart items
    cursor.execute("""
                   SELECT C.*, P.UnitPrice, P.Discount
                   FROM Carts C
                            JOIN Products P ON C.ProductID = P.ProductID
                   WHERE CustomerID = %s
                   """, (customer_id,))
    cart_items = cursor.fetchall()

    if not cart_items:
        cursor.close()
        conn.close()
        return redirect(url_for('shop_page'))

    total_amount = sum(((item['UnitPrice'] - item['Discount']) * item['Quantity']) for item in cart_items)

    try:
        # 2. Check Total Global Stock for every item first
        for item in cart_items:
            cursor.execute("SELECT SUM(Quantity) as global_qty FROM WarehouseStock WHERE ProductID = %s",
                           (item['ProductID'],))
            row = cursor.fetchone()
            global_stock = row['global_qty'] if row['global_qty'] else 0

            if global_stock < item['Quantity']:
                return f"Error: Not enough total stock for {item['ProductID']}. Available: {global_stock}", 400

        # 3. Create Transaction
        cursor.execute("""
                       INSERT INTO Transactions (TransactionTimestamp, TotalAmount, CustomerID, EmployeeID)
                       VALUES (%s, %s, %s, %s)
                       """, (datetime.now(), total_amount, customer_id, 1))
        transaction_id = cursor.lastrowid

        # 4. Deduct Stock and Record Items
        for item in cart_items:
            remaining_to_deduct = item['Quantity']
            price_paid = item['UnitPrice'] - item['Discount']

            # Record historical sale
            cursor.execute("""
                           INSERT INTO TransactionItems (TransactionID, ProductID, Quantity, PriceAtTimeOfSale)
                           VALUES (%s, %s, %s, %s)
                           """, (transaction_id, item['ProductID'], item['Quantity'], price_paid))

            # Deduct from warehouses sequentially
            cursor.execute(
                "SELECT WarehouseID, Quantity FROM WarehouseStock WHERE ProductID = %s AND Quantity > 0 ORDER BY WarehouseID ASC",
                (item['ProductID'],))
            stocks = cursor.fetchall()

            for stock in stocks:
                if remaining_to_deduct <= 0:
                    break

                if stock['Quantity'] >= remaining_to_deduct:
                    # Current warehouse can cover the rest
                    cursor.execute(
                        "UPDATE WarehouseStock SET Quantity = Quantity - %s WHERE WarehouseID = %s AND ProductID = %s",
                        (remaining_to_deduct, stock['WarehouseID'], item['ProductID']))
                    remaining_to_deduct = 0
                else:
                    # Drain this warehouse and move to next
                    cursor.execute("UPDATE WarehouseStock SET Quantity = 0 WHERE WarehouseID = %s AND ProductID = %s",
                                   (stock['WarehouseID'], item['ProductID']))
                    remaining_to_deduct -= stock['Quantity']

        # 5. Clear Cart
        cursor.execute("DELETE FROM Carts WHERE CustomerID = %s", (customer_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Database Error: {str(e)}", 500
    finally:
        cursor.close()
        conn.close()

    return render_template('checkout_success.html', transaction_id=transaction_id)
@app.route('/admin')
def admin():
    # 1. Check if user is logged in
    user_id = session.get('user_id')
    user_role = session.get('role')

    # 2. Verify they have the 'Admin' role
    if not user_id or user_role != 'Admin':
        return redirect(url_for('login'))

    # 3. If they are an Admin, proceed to fetch data for the dashboard
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total revenue
    cursor.execute("SELECT SUM(TotalAmount) AS Total FROM Transactions")
    total_revenue = cursor.fetchone()

    cursor.execute("SELECT count(CustomerID) AS Total FROM Customers")
    customer_count = cursor.fetchone()

    cursor.execute("SELECT count(ProductID) AS Total FROM Products")
    product_count = cursor.fetchone()

    # Top 3 best sellers
    cursor.execute("""
        SELECT P.Name, COALESCE(SUM(T.Quantity * T.PriceAtTimeOfSale), 0) AS TotalRevenue
        FROM TransactionItems T
        JOIN Products P ON T.ProductID = P.ProductID
        GROUP BY P.ProductID, P.Name
        ORDER BY TotalRevenue DESC
        LIMIT 3
        """)
    top_sellers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'admin.html',
        total_revenue=total_revenue,
        customer_count=customer_count,
        product_count=product_count,
        top_sellers=top_sellers
    )

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
        ORDER BY P.ProductID
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
    return render_template('admin_warehouse_product.html', product=product,Ware_id=Ware_id)

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

@app.route('/add_warehouse_product/<int:Ware_id>', methods=['GET','POST'])
def add_warehouse_product(Ware_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        product_id = request.form['product_id']
        quantity = request.form['quantity']

        cursor2 = conn.cursor()
        cursor2.execute("""
                    INSERT INTO warehousestock (WarehouseID,ProductID,Quantity) 
                    values(%s,%s,%s)
        """, (Ware_id, product_id,quantity))
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_warehouse_product',Ware_id=Ware_id))


    cursor.execute("""select P.ProductID,P.Name
                                from products P
                                where (P.ProductID,P.Name) NOT IN (SELECT P.ProductID,P.Name
                                from products P LEFT join warehousestock w on P.ProductID = W.ProductID
                                WHERE W.WarehouseID = %s)""",
                   (Ware_id,))
    product = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('add_warehouse_product.html', product=product,Ware_id=Ware_id)

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

########################################################################################################################
########################################    Categories      #############################################################
########################################################################################################################
@app.route('/admin_category')
def admin_category():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT CategoryID, Name FROM Categories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_category.html', categories=categories)

@app.route('/add_category', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        name = request.form['name']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Categories (Name) VALUES (%s)", (name,))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('admin_category'))

    return render_template('add_category.html')

@app.route('/edit_category/<int:cat_id>', methods=['GET', 'POST'])
def edit_category(cat_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        cursor2 = conn.cursor()
        cursor2.execute(
            "UPDATE Categories SET Name=%s WHERE CategoryID=%s",
            (name, cat_id)
        )
        conn.commit()
        cursor2.close()

        cursor.close()
        conn.close()
        return redirect(url_for('admin_category'))

    cursor.execute("SELECT * FROM Categories WHERE CategoryID=%s", (cat_id,))
    category = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('edit_category.html', category=category)

@app.route('/delete_category/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM Categories WHERE CategoryID=%s", (cat_id,))
        conn.commit()
        msg = "Category deleted successfully"
        msg_type = "success"

    except mysql.connector.Error as err:

            msg = "Cannot delete this category because it has products. Move/delete products first."
            msg_type = "error"

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_category', msg=msg, type=msg_type))
########################################################################################################################
########################################  Transaction ###############################################################
########################################################################################################################
@app.route('/admin_transaction')
def admin_transaction():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            T.TransactionID,
            T.TransactionTimestamp,
            T.TotalAmount,
            CONCAT(C.FirstName, ' ', C.LastName) AS CustomerName
        FROM Transactions T LEFT JOIN Customers C ON T.CustomerID = C.CustomerID
        ORDER BY T.TransactionID
    """)
    transactions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_transaction.html', transactions=transactions)


@app.route('/admin_transaction/<int:transaction_id>')
def admin_transaction_details(transaction_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            T.TransactionID,
            T.TransactionTimestamp,
            T.TotalAmount,
            CONCAT(C.FirstName, ' ', C.LastName) AS CustomerName,
            CONCAT(E.FirstName, ' ', E.LastName) AS EmployeeName
        FROM Transactions T
        LEFT JOIN Customers C ON T.CustomerID = C.CustomerID
        LEFT JOIN Employees E ON T.EmployeeID = E.EmployeeID
        WHERE T.TransactionID = %s
    """, (transaction_id,))
    txn = cursor.fetchone()

    cursor.execute("""
        SELECT
            P.Name,
            TI.Quantity,
            TI.PriceAtTimeOfSale,
            (TI.Quantity * TI.PriceAtTimeOfSale) AS LineTotal
        FROM TransactionItems TI
        JOIN Products P ON TI.ProductID = P.ProductID
        WHERE TI.TransactionID = %s
    """, (transaction_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_transaction_details.html', txn=txn, items=items)


    return redirect(url_for('admin_employee'))
if __name__ == '__main__':
    app.run(debug=True)