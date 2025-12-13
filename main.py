from flask import Flask, render_template
import mysql.connector

app = Flask(__name__)

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'supermarket_admin',
    'password': 'admin123',
    'database': 'Supermarket'
}
#hhhhhhhhhhhrrrrrrrrrr
def get_db_connection():
    return mysql.connector.connect(**db_config)


@app.route('/')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)


    # 1. Search for "Organic" Products
    cursor.execute("SELECT * FROM Products WHERE Name LIKE '%Organic%'")
    organic_products = cursor.fetchall()

    # 2. Check Stock at Warehouse 1
    cursor.execute("""
                   SELECT P.Name, WS.Quantity
                   FROM WarehouseStock WS
                            JOIN Products P ON WS.ProductID = P.ProductID
                   WHERE WS.WarehouseID = 1
                   """)
    stock_levels = cursor.fetchall()

    # 3. Top 3 Best-Selling Products by Revenue
    cursor.execute("""
                   SELECT P.Name, SUM(TI.Quantity * TI.PriceAtTimeOfSale) as TotalRevenue
                   FROM TransactionItems TI
                            JOIN Products P ON TI.ProductID = P.ProductID
                   GROUP BY P.ProductID
                   ORDER BY TotalRevenue DESC LIMIT 3
                   """)
    top_sellers = cursor.fetchall()

    # 4. Total Revenue Single Value
    cursor.execute("SELECT SUM(TotalAmount) as Total FROM Transactions")
    total_revenue = cursor.fetchone()['Total']

    cursor.close()
    conn.close()

    return render_template('dashboard.html',
                           organic_products=organic_products,
                           stock_levels=stock_levels,
                           top_sellers=top_sellers,
                           total_revenue=total_revenue)


if __name__ == '__main__':
    app.run(debug=True)