from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import csv
import io

app = Flask(__name__)
DATABASE = 'pharmacy.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER,
            price REAL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    search_query = request.args.get('search', '').strip()

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    if search_query:
        cur.execute("SELECT * FROM medicines WHERE name LIKE ?", ('%' + search_query + '%',))
    else:
        cur.execute("SELECT * FROM medicines")

    medicines = cur.fetchall()
    conn.close()

    return render_template('index.html', medicines=medicines, search_query=search_query)

@app.route('/add', methods=['POST'])
def add():
    name = request.form['name']
    quantity = int(request.form['quantity'])
    price = float(request.form['price'])

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("INSERT INTO medicines (name, quantity, price) VALUES (?, ?, ?)",
                (name, quantity, price))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("DELETE FROM medicines WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])

        cur.execute("UPDATE medicines SET name = ?, quantity = ?, price = ? WHERE id = ?",
                    (name, quantity, price, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    else:
        cur.execute("SELECT * FROM medicines WHERE id = ?", (id,))
        medicine = cur.fetchone()
        conn.close()
        if medicine:
            return render_template('edit.html', medicine=medicine)
        else:
            return "Medicine not found", 404

@app.route('/download')
def download():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM medicines")
    medicines = cur.fetchall()
    conn.close()

    # Create CSV in memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Quantity', 'Price'])
    cw.writerows(medicines)

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(output,
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='pharmacy_inventory.csv')

if __name__ == '__main__':
    print("Starting Flask server on http://127.0.0.1:5000")
    init_db()
    app.run(debug=True)

