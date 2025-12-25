from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

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