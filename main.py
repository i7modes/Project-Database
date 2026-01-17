from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'alsalam_supermarket_secret_key_2025'

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'database': 'Supermarket'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)


@app.route('/')
@app.route('/shop')
def shop_page():
    search_query = request.args.get('q', '')
    category_id = request.args.get('category', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Categories")
    categories = cursor.fetchall()

    base_query = "SELECT P.*, Cat.Name AS CategoryName, (SELECT SUM(Quantity) FROM WarehouseStock WHERE ProductID = P.ProductID) AS TotalStock FROM Products P LEFT JOIN Categories Cat ON P.CategoryID = Cat.CategoryID WHERE 1 = 1"
    params = []

    if search_query:
        base_query += " AND P.Name LIKE %s"
        params.append(f"%{search_query}%")

    if category_id:
        base_query += " AND P.CategoryID = %s"
        params.append(category_id)

    cursor.execute(base_query, params)
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('shop.html',
                           products=products,
                           categories=categories,
                           search_query=search_query,
                           category_id=category_id)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Customers WHERE Email = %s AND Password = %s", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user['CustomerID']
            session['role'] = 'customer'
            session['user_name'] = user['FirstName']
            cursor.close()
            conn.close()
            return redirect(url_for('shop_page'))

        cursor.execute("SELECT * FROM Employees WHERE Email = %s AND Password = %s", (email, password))
        employee = cursor.fetchone()

        cursor.close()
        conn.close()

        if employee:
            session['user_id'] = employee['EmployeeID']
            session['role'] = employee['Role']
            session['user_name'] = employee['FirstName']
            return redirect(url_for('shop_page'))

        error = "Invalid email or password. Please try again."

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('shop_page'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Customers WHERE Email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            error = "This email is already registered. Please use a different one."
            return render_template('register.html', error=error)

        query = """
                INSERT INTO Customers (FirstName, LastName, Email, Password, Phone, Address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
        cursor.execute(query, (first_name, last_name, email, password, phone, address))
        conn.commit()

        new_user_id = cursor.lastrowid
        session['user_id'] = new_user_id
        session['user_name'] = first_name
        session['role'] = 'customer'

        cursor.close()
        conn.close()
        return redirect(url_for('shop_page'))

    return render_template('register.html', error=error)


@app.route('/customer_panel')
def customer_panel():
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'customer':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(TotalAmount) as total, COUNT(*) as count FROM Transactions WHERE CustomerID = %s", (user_id,))
    stats = cursor.fetchone()
    total_spent = stats['total'] if stats['total'] else 0
    order_count = stats['count']

    cursor.execute("SELECT SUM(Quantity) as cart_total FROM Carts WHERE CustomerID = %s", (user_id,))
    cart_res = cursor.fetchone()
    cart_count = cart_res['cart_total'] if cart_res['cart_total'] else 0

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

    cursor.execute("""
        SELECT * FROM Transactions 
        WHERE TransactionID = %s AND CustomerID = %s
    """, (transaction_id, user_id))
    order = cursor.fetchone()

    if not order:
        cursor.close()
        conn.close()
        return "Order not found or access denied.", 403

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

    cursor.execute("SELECT * FROM Customers WHERE CustomerID = %s", (user_id,))
    user_data = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user_data)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    user_id = session.get('user_id')
    user_role = session.get('role')

    if not user_id:
        return redirect(url_for('login'))

    if user_role in ['Admin', 'Staff']:
        return redirect(url_for('shop_page'))

    product_id = request.form.get('product_id')
    conn = get_db_connection()
    cursor = conn.cursor()

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
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
                   DELETE
                   FROM Carts
                   WHERE CustomerID = %s
                     AND ProductID = %s
                   """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('view_cart', customer_id=user_id))


@app.route('/update_cart', methods=['POST'])
def update_cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

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
                    cursor.execute("DELETE FROM Carts WHERE CustomerID = %s AND ProductID = %s", (user_id, product_id))
            except ValueError:
                continue

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('view_cart', customer_id=user_id))

@app.route('/cart/<int:customer_id>')
def view_cart(customer_id):
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

    cursor.execute("""
                   SELECT C.*, P.UnitPrice, P.Discount, P.Name
                   FROM Carts C
                            JOIN Products P ON C.ProductID = P.ProductID
                   WHERE CustomerID = %s
                   """, (customer_id,))
    cart_items = cursor.fetchall()

    total_amount = sum(((item['UnitPrice'] - item['Discount']) * item['Quantity']) for item in cart_items)

    try:
        if not cart_items:
            return redirect(url_for('shop_page'))

        for item in cart_items:
            cursor.execute("SELECT SUM(Quantity) as global_qty FROM WarehouseStock WHERE ProductID = %s",
                           (item['ProductID'],))
            row = cursor.fetchone()
            global_stock = row['global_qty'] if row['global_qty'] else 0

            if global_stock < item['Quantity']:
                error = f"Not enough stock for {item['Name']}. Available: {global_stock}"
                return render_template('cart.html', items=cart_items, total=total_amount, customer_id=customer_id,
                                       error=error)

        cursor.execute("""
                       INSERT INTO Transactions (TransactionTimestamp, TotalAmount, CustomerID)
                       VALUES (%s, %s, %s)
                       """, (datetime.now(), total_amount, customer_id))
        transaction_id = cursor.lastrowid

        for item in cart_items:
            remaining_to_deduct = item['Quantity']
            price_paid = item['UnitPrice'] - item['Discount']

            cursor.execute("""
                           INSERT INTO TransactionItems (TransactionID, ProductID, Quantity, PriceAtTimeOfSale)
                           VALUES (%s, %s, %s, %s)
                           """, (transaction_id, item['ProductID'], item['Quantity'], price_paid))

            cursor.execute(
                "SELECT WarehouseID, Quantity FROM WarehouseStock WHERE ProductID = %s AND Quantity > 0 ORDER BY WarehouseID ASC",
                (item['ProductID'],))
            stocks = cursor.fetchall()

            for stock in stocks:
                if remaining_to_deduct <= 0:
                    break
                if stock['Quantity'] >= remaining_to_deduct:
                    cursor.execute(
                        "UPDATE WarehouseStock SET Quantity = Quantity - %s WHERE WarehouseID = %s AND ProductID = %s",
                        (remaining_to_deduct, stock['WarehouseID'], item['ProductID']))
                    remaining_to_deduct = 0
                else:
                    cursor.execute("UPDATE WarehouseStock SET Quantity = 0 WHERE WarehouseID = %s AND ProductID = %s",
                                   (stock['WarehouseID'], item['ProductID']))
                    remaining_to_deduct -= stock['Quantity']

        cursor.execute("DELETE FROM Carts WHERE CustomerID = %s", (customer_id,))
        conn.commit()

        return render_template('checkout_success.html', transaction_id=transaction_id)

    except Exception as e:
        conn.rollback()
        return render_template('cart.html', items=cart_items, total=total_amount, customer_id=customer_id,
                               error=f"Checkout Error: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@app.route('/admin')
def admin():
    user_id = session.get('user_id')
    user_role = session.get('role')

    if not user_id or user_role != 'Admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(TotalAmount) AS Total FROM Transactions")
    total_revenue = cursor.fetchone()

    cursor.execute("SELECT count(CustomerID) AS Total FROM Customers")
    customer_count = cursor.fetchone()

    cursor.execute("SELECT count(ProductID) AS Total FROM Products")
    product_count = cursor.fetchone()

    cursor.execute("""
        SELECT P.Name, SUM(T.Quantity * T.PriceAtTimeOfSale) AS TotalRevenue
        FROM TransactionItems T
        join Products P ON T.ProductID = P.ProductID
        Group By P.ProductID, P.Name
        ORDER BY TotalRevenue DESC
        limit 3
        """)
    top_sellers = cursor.fetchall()

    cursor.execute("""
            SELECT DATE(T.TransactionTimestamp) AS Day,SUM(T.TotalAmount) AS Revenue, COUNT(*) AS TransactionsCount
            FROM Transactions T
            WHERE T.TransactionTimestamp >= (NOW() - INTERVAL 1 DAY)
            Group by DATE(T.TransactionTimestamp)
            ORDER BY Day DESC
        """)
    sales_today = cursor.fetchall()

    cursor.execute("""
            SELECT DATE(T.TransactionTimestamp) AS Day,SUM(T.TotalAmount) AS Revenue, COUNT(*) AS TransactionsCount
            FROM Transactions T
            WHERE T.TransactionTimestamp >= (NOW() - INTERVAL 7 DAY)
            Group by DATE(T.TransactionTimestamp)
            ORDER BY Day DESC
        """)
    sales_last_7_days = cursor.fetchall()

    cursor.execute("""
            SELECT P.ProductID, P.Name,SUM(WS.Quantity) AS TotalQty
            FROM Products P left join WarehouseStock WS ON WS.ProductID = P.ProductID
            Group By P.ProductID, P.Name
            HAVING TotalQty = 0
            ORDER BY P.Name
            LIMIT 10
        """)
    out_of_stock = cursor.fetchall()

    cursor.execute("""
            SELECT P.ProductID, P.Name,SUM(WS.Quantity) AS TotalQty
            FROM Products P left join WarehouseStock WS ON WS.ProductID = P.ProductID
            GROUP BY P.ProductID, P.Name
            HAVING TotalQty > 0 AND TotalQty < 5
            ORDER BY TotalQty ASC
            LIMIT 10
        """)
    low_stock = cursor.fetchall()

    cursor.execute("""
            SELECT C.CustomerID,CONCAT(C.FirstName,' ',C.LastName) AS CustomerName,COUNT(T.TransactionID) AS OrdersCount,SUM(T.TotalAmount) AS TotalSpent
            FROM Transactions T JOIN Customers C ON C.CustomerID = T.CustomerID
            Group By C.CustomerID, CustomerName
            ORDER BY TotalSpent DESC
            LIMIT 5
        """)
    top_customers = cursor.fetchall()


    cursor.execute("""
        SELECT P.ProductID,P.Name,SUM(T.Quantity) AS UnitsSold
        FROM TransactionItems T JOIN Products P ON P.ProductID = T.ProductID
        GROUP BY P.ProductID, P.Name
        ORDER BY UnitsSold DESC
        LIMIT 5
    """)
    most_sold_products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'admin.html',
        total_revenue=total_revenue,
        customer_count=customer_count,
        product_count=product_count,
        most_sold_products=most_sold_products,
        top_sellers=top_sellers,
        sales_today=sales_today,
        sales_last_7_days=sales_last_7_days,
        out_of_stock=out_of_stock,
        low_stock=low_stock,
        top_customers=top_customers
    )

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
    cursor = conn.cursor(dictionary=True)
    error = None

    try:
        cursor.execute("DELETE FROM Customers WHERE CustomerID = %s", (customer_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_customer'))

    except mysql.connector.Error as err:
            error = "Cannot delete this customer because they have existing order history."


    cursor.execute("SELECT CustomerID, FirstName, LastName, Phone, Address FROM Customers")
    customers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_customer.html', customer=customers, error=error)


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
        first_name= request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        role = request.form['role']

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

@app.route('/admin_product')
def admin_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

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
        return redirect(url_for('admin_product'))

    cursor = conn.cursor(dictionary=True)
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
        image_url = request.form.get('image_url')

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
    cursor = conn.cursor(dictionary=True)
    error = None

    try:
        cursor.execute("DELETE FROM Products WHERE ProductID=%s", (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_product'))

    except mysql.connector.Error as err:
            error = "Cannot delete this product because it has been sold in previous transactions."


    cursor.execute("""
                   SELECT P.ProductID,P.Name,P.UnitPrice,P.Discount,P.ImageURL,C.Name AS CategoryName,P.CategoryID
                   FROM Products P LEFT JOIN Categories C ON P.CategoryID = C.CategoryID
                   ORDER BY P.ProductID
                   """)
    products = cursor.fetchall()

    cursor.execute("SELECT CategoryID, Name FROM Categories ORDER BY Name")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_product.html', products=products, categories=categories, error=error)

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
    cursor = conn.cursor(dictionary=True)
    error = None

    try:
        cursor.execute("DELETE FROM Categories WHERE CategoryID=%s", (cat_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_category'))

    except mysql.connector.Error as err:
            error = "Cannot delete this category because it contains products. Please delete or move the products first."


    cursor.execute("SELECT CategoryID, Name FROM Categories")
    categories = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_category.html', categories=categories, error=error)

@app.route('/admin_transaction')
def admin_transaction():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT T.TransactionID,T.TransactionTimestamp,T.TotalAmount,CONCAT(C.FirstName, ' ', C.LastName) AS CustomerName
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
        SELECT T.TransactionID,T.TransactionTimestamp,T.TotalAmount,CONCAT(C.FirstName, ' ', C.LastName) AS CustomerName
        FROM Transactions T
        left join Customers C ON T.CustomerID = C.CustomerID
        WHERE T.TransactionID = %s
    """, (transaction_id,))
    detail = cursor.fetchone()

    cursor.execute("""
        SELECT P.Name,T.Quantity,T.PriceAtTimeOfSale,(T.Quantity * T.PriceAtTimeOfSale) AS LineTotal
        FROM TransactionItems T
        JOIN Products P ON T.ProductID = P.ProductID
        WHERE T.TransactionID = %s
    """, (transaction_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_transaction_details.html', detail=detail, items=items)

if __name__ == '__main__':
    app.run(debug=True)