import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, Response
from functools import wraps
import csv
from io import StringIO
import io




app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this in production!

DATABASE = 'pharmacy.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    # Create default admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', 'admin123'))

    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    total_medicines = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    total_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    total_sales = conn.execute("SELECT SUM(quantity) FROM sales").fetchone()[0] or 0
    low_stock = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < 10").fetchone()[0]
    conn.close()
    return render_template('dashboard.html',
                           total_medicines=total_medicines,
                           total_patients=total_patients,
                           total_sales=total_sales,
                           low_stock=low_stock)

from flask import request

@app.route('/medicines')
@login_required
def medicines():
    search = request.args.get('search', '')  # get search query or empty string
    conn = get_db_connection()

    if search:
        meds = conn.execute(
            "SELECT * FROM medicines WHERE name LIKE ?", ('%' + search + '%',)
        ).fetchall()
    else:
        meds = conn.execute('SELECT * FROM medicines').fetchall()

    conn.close()
    return render_template('medicines.html', medicines=meds, search=search)

@app.route('/medicine/add', methods=['GET', 'POST'])
@login_required
def add_medicine():
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        conn = get_db_connection()
        conn.execute('INSERT INTO medicines (name, quantity, price) VALUES (?, ?, ?)', (name, quantity, price))
        conn.commit()
        conn.close()
        flash('Medicine added successfully', 'success')
        return redirect(url_for('medicines'))
    return render_template('add_medicine.html')

@app.route('/medicine/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_medicine(id):
    conn = get_db_connection()
    med = conn.execute('SELECT * FROM medicines WHERE id = ?', (id,)).fetchone()
    if not med:
        conn.close()
        flash('Medicine not found', 'danger')
        return redirect(url_for('medicines'))
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        conn.execute('UPDATE medicines SET name = ?, quantity = ?, price = ? WHERE id = ?', (name, quantity, price, id))
        conn.commit()
        conn.close()
        flash('Medicine updated successfully', 'success')
        return redirect(url_for('medicines'))
    conn.close()
    return render_template('edit_medicine.html', medicine=med)

@app.route('/medicine/delete/<int:id>', methods=['POST'])
@login_required
def delete_medicine(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM medicines WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Medicine deleted successfully', 'success')
    return redirect(url_for('medicines'))

@app.route('/patients')
@login_required
def patients():
    search_query = request.args.get('search', '').strip()

    conn = get_db_connection()
    if search_query:
        # Using LIKE for partial matching; adjust fields as needed
        patients = conn.execute(
            "SELECT * FROM patients WHERE name LIKE ? OR email LIKE ?",
            (f'%{search_query}%', f'%{search_query}%')
        ).fetchall()
    else:
        patients = conn.execute('SELECT * FROM patients').fetchall()

    conn.close()
    return render_template('patients.html', patients=patients, search=search_query)
@app.route('/patient/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        conn = get_db_connection()
        conn.execute('INSERT INTO patients (name, phone) VALUES (?, ?)', (name, phone))
        conn.commit()
        conn.close()
        flash('Patient added successfully', 'success')
        return redirect(url_for('patients'))
    return render_template('add_patient.html')

@app.route('/sales')
@login_required
def sales():
    conn = get_db_connection()
    sales_data = conn.execute('''
        SELECT sales.id, medicines.name AS medicine_name, patients.name AS patient_name, sales.quantity, sales.date
        FROM sales
        JOIN medicines ON sales.medicine_id = medicines.id
        JOIN patients ON sales.patient_id = patients.id
        ORDER BY sales.date DESC
    ''').fetchall()
    conn.close()
    return render_template('sales.html', sales=sales_data)

@app.route('/sale/add', methods=['GET', 'POST'])
@login_required
def add_sale():
    conn = get_db_connection()
    medicines = conn.execute('SELECT * FROM medicines').fetchall()
    patients = conn.execute('SELECT * FROM patients').fetchall()

    if request.method == 'POST':
        medicine_id = int(request.form['medicine_id'])
        patient_id = int(request.form['patient_id'])
        quantity = int(request.form['quantity'])

        # Check stock
        stock_row = conn.execute('SELECT quantity FROM medicines WHERE id = ?', (medicine_id,)).fetchone()
        if not stock_row:
            flash('Selected medicine not found', 'danger')
            conn.close()
            return render_template('add_sale.html', medicines=medicines, patients=patients)

        stock = stock_row['quantity']
        if quantity > stock:
            flash('Not enough stock for this medicine', 'danger')
            conn.close()
            return render_template('add_sale.html', medicines=medicines, patients=patients)

        # Insert sale and update stock
        conn.execute('INSERT INTO sales (medicine_id, patient_id, quantity) VALUES (?, ?, ?)',
                     (medicine_id, patient_id, quantity))
        conn.execute('UPDATE medicines SET quantity = quantity - ? WHERE id = ?', (quantity, medicine_id))

        conn.commit()
        conn.close()

        flash('Sale recorded successfully', 'success')
        return redirect(url_for('sales'))

    conn.close()
    return render_template('add_sale.html', medicines=medicines, patients=patients)

@app.route('/download')
@login_required
def download():
    conn = get_db_connection()
    medicines = conn.execute('SELECT id, name, quantity, price FROM medicines').fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Quantity', 'Price'])
    for med in medicines:
        cw.writerow([med['id'], med['name'], med['quantity'], med['price']])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=inventory.csv'}
    )

@app.route('/edit_patient/<int:id>', methods=['GET', 'POST'])
def edit_patient(id):
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        phone = request.form['phone']
        conn.execute('UPDATE patients SET name = ?, age = ?, phone = ? WHERE id = ?', (name, age, phone, id))
        conn.commit()
        conn.close()
        return redirect(url_for('patients'))

    patient = conn.execute('SELECT * FROM patients WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:id>')
def delete_patient(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM patients WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('patients'))


from flask import Response

@app.route('/download_sales')
@login_required
def download_sales():
    conn = get_db_connection()
    sales = conn.execute('SELECT * FROM sales').fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV header row
    writer.writerow(['ID', 'Medicine ID', 'Patient ID', 'Quantity', 'Date'])

    # Write data rows
    for sale in sales:
        writer.writerow([sale['id'], sale['medicine_id'], sale['patient_id'], sale['quantity'], sale['date']])

    csv_content = output.getvalue()
    output.close()

    # ✅ Return as downloadable CSV file
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={
            "Content-disposition": "attachment; filename=sales_data.csv"
        }
    )


import sqlite3
from collections import defaultdict
from flask import render_template

@app.route('/sales/analytics')
def sales_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total profit per patient (for pie chart)
    cursor.execute("""
        SELECT patients.name, SUM(medicines.price * sales.quantity) AS total_profit
        FROM sales
        JOIN patients ON sales.patient_id = patients.id
        JOIN medicines ON sales.medicine_id = medicines.id
        GROUP BY patients.name
    """)
    profit_data = cursor.fetchall()

    # Most frequent patient
    cursor.execute("""
        SELECT patients.name, COUNT(*) AS frequency
        FROM sales
        JOIN patients ON sales.patient_id = patients.id
        GROUP BY patients.id
        ORDER BY frequency DESC
        LIMIT 1
    """)
    most_frequent_patient = cursor.fetchone()

    # Highest profit-contributing patient
    cursor.execute("""
        SELECT patients.name, SUM(medicines.price * sales.quantity) AS total_profit
        FROM sales
        JOIN patients ON sales.patient_id = patients.id
        JOIN medicines ON sales.medicine_id = medicines.id
        GROUP BY patients.id
        ORDER BY total_profit DESC
        LIMIT 1
    """)
    top_profit_patient = cursor.fetchone()

    # Most sold medicine
    cursor.execute("""
        SELECT medicines.name, SUM(sales.quantity) AS total_sold
        FROM sales
        JOIN medicines ON sales.medicine_id = medicines.id
        GROUP BY medicines.id
        ORDER BY total_sold DESC
        LIMIT 1
    """)
    most_sold_medicine = cursor.fetchone()

    # Least sold medicine
    cursor.execute("""
        SELECT medicines.name, SUM(sales.quantity) AS total_sold
        FROM sales
        JOIN medicines ON sales.medicine_id = medicines.id
        GROUP BY medicines.id
        ORDER BY total_sold ASC
        LIMIT 1
    """)
    least_sold_medicine = cursor.fetchone()

    conn.close()

    return render_template("sales_analytics.html",
                           profit_data=profit_data,
                           most_frequent_patient=most_frequent_patient,
                           top_profit_patient=top_profit_patient,
                           most_sold_medicine=most_sold_medicine,
                           least_sold_medicine=least_sold_medicine)




from io import BytesIO
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from flask import request, make_response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import base64

@app.route('/analytics/export/pdf', methods=['POST'])
def export_analytics_pdf():
    data = request.get_json()
    chart_base64 = data.get('chart', None)
    analytics = data.get('analytics', {})

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 750, "Sales Analytics Report")

    if chart_base64:
        header, encoded = chart_base64.split(",", 1)
        chart_data = base64.b64decode(encoded)
        image = ImageReader(io.BytesIO(chart_data))
        c.drawImage(image, 50, 400, width=500, height=300)

    c.setFont("Helvetica", 12)
    c.drawString(50, 380, "Insights:")

    y = 360
    for key, value in analytics.items():
        c.drawString(60, y, f"{key.replace('_', ' ').title()}: {value}")
        y -= 20

    c.showPage()
    c.save()

    buffer.seek(0)
    return make_response(buffer.getvalue(), {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="sales_analytics.pdf"'
    })

from flask import Response




if __name__ == '__main__':
    init_db()
    app.run(debug=True)

