from flask import Flask, render_template, request, redirect, url_for
import mysql.connector

app = Flask(__name__)

# Database Configuration
db_config = {
    'host': 'database.renthic.space',
    'user': 'supermarket_admin',
    'password': 'Admin123!',
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

    cursor.execute("SELECT * FROM Products")
    organic_products = cursor.fetchall()

    #Top 3 Best-Selling Products by Revenue
    cursor.execute("""
                   SELECT P.Name, SUM(TI.Quantity * TI.PriceAtTimeOfSale) as TotalRevenue
                   FROM TransactionItems TI
                            JOIN Products P ON TI.ProductID = P.ProductID
                   GROUP BY P.ProductID
                   ORDER BY TotalRevenue DESC LIMIT 3
                   """)
    top_sellers = cursor.fetchall()

    #Total Revenue Single Value
    cursor.execute("SELECT SUM(TotalAmount) as Total FROM Transactions")
    total_revenue = cursor.fetchone()['Total']

    cursor.close()
    conn.close()
    return render_template('dashboard.html',
                           organic_products=organic_products,
                           customer=customer,
                           top_sellers=top_sellers,
                           total_revenue=total_revenue)

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


if __name__ == '__main__':
    app.run(debug=True)