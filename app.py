from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os
from datetime import datetime
import random

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # Replace with your MySQL username
app.config['MYSQL_PASSWORD'] = ''  # Replace with your MySQL password
app.config['MYSQL_DB'] = 'exchangedb'
app.secret_key = 'your_secret_key'

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'

mysql = MySQL(app)

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


# Send Transfer
@app.route('/send_transfer', methods=['POST'])
def send_transfer():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        sender_account_id = request.form.get('sender_account_id', None)
        sender_name = request.form.get('sender_name', '')
        receiver_name = request.form['receiver_name']
        receiver_place = request.form['receiver_place']
        amount = float(request.form['amount'])
        currency = request.form['currency']
        commission = float(request.form.get('commission', 0))
        note = request.form.get('note', '')
        branch = request.form['branch']

        cur = mysql.connection.cursor()

        if sender_account_id:
            # Deduct amount + commission from the sender account
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (sender_account_id,))
            sender_balance = cur.fetchone()[0]

            if sender_balance < (amount + commission):
                flash('Insufficient balance in the sender account.', 'error')
                return redirect(url_for('transfers'))

            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                        (amount + commission, sender_account_id))

        # Record the send transfer
        cur.execute("INSERT INTO send_transfers (sender_account_id, sender_name, receiver_name, receiver_place, amount, currency, commission, note, branch) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (sender_account_id, sender_name, receiver_name, receiver_place, amount, currency, commission, note, branch))

        mysql.connection.commit()
        cur.close()
        flash('Send transfer completed successfully!', 'success')
    return redirect(url_for('transfers'))


# Home Page
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM company_info")
    company_info = cur.fetchone()

    # Fetch total balances in all currencies
    cur.execute("SELECT currency, SUM(balance) as total FROM accounts GROUP BY currency")
    total_balances = cur.fetchall()

    # Fetch recent transactions
    cur.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 5")
    recent_transactions = cur.fetchall()

    # Fetch online user
    cur.execute("SELECT username FROM users WHERE user_id = %s", (session['user_id'],))
    online_user = cur.fetchone()

    cur.close()

    return render_template('index.html', company_info=company_info, total_balances=total_balances,
                          recent_transactions=recent_transactions, online_user=online_user)


# Chart of Accounts Page
@app.route('/accounts')
def accounts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch accounts
    cur.execute("SELECT * FROM accounts")
    accounts = cur.fetchall()

    # Fetch account types
    cur.execute("SELECT * FROM account_types")
    account_types = cur.fetchall()

    # Fetch currencies
    cur.execute("SELECT * FROM currencies")
    currencies = cur.fetchall()

    cur.close()

    return render_template('accounts.html', accounts=accounts, account_types=account_types, currencies=currencies)


# Add Account
@app.route('/add_account', methods=['POST'])
def add_account():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        account_name = request.form['account_name']
        account_type = request.form['account_type']
        currency = request.form['currency']
        balance = float(request.form['balance'])

        # Generate a random account number starting with 2025
        account_number = f"2025{random.randint(1000, 9999)}"

        cur = mysql.connection.cursor()

        # Check if the account number already exists
        cur.execute("SELECT * FROM accounts WHERE account_number = %s", (account_number,))
        if cur.fetchone():
            flash('Account number already exists. Please try again.', 'error')
            return redirect(url_for('accounts'))

        # Insert the new account
        cur.execute("INSERT INTO accounts (account_name, account_type, currency, balance, account_number) VALUES (%s, %s, %s, %s, %s)",
                    (account_name, account_type, currency, balance, account_number))
        mysql.connection.commit()
        cur.close()
        flash('Account added successfully!', 'success')
    return redirect(url_for('accounts'))


# Transfers Page
@app.route('/transfers')
def transfers():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch accounts for dropdowns
    cur.execute("SELECT * FROM accounts")
    accounts = cur.fetchall()

    # Fetch currencies for dropdowns
    cur.execute("SELECT * FROM currencies")
    currencies = cur.fetchall()

    cur.close()

    return render_template('transfers.html', accounts=accounts, currencies=currencies)


@app.route('/transfer_between_accounts', methods=['POST'])
def transfer_between_accounts():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Get form data
            from_account_id = request.form['from_account_id']
            to_account_id = request.form['to_account_id']
            amount = float(request.form['amount'])
            note = request.form.get('note', '')

            cur = mysql.connection.cursor()

            # Check if From Account has enough balance
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (from_account_id,))
            from_account_balance = cur.fetchone()[0]

            if from_account_balance < amount:
                flash('Insufficient balance in the From Account.', 'error')
                return redirect(url_for('transfers'))

            # Deduct amount from From Account
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                        (amount, from_account_id))

            # Add amount to To Account
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s",
                        (amount, to_account_id))

            # Record the transfer
            cur.execute("INSERT INTO transfers_between_accounts (from_account_id, to_account_id, amount, note) VALUES (%s, %s, %s, %s)",
                        (from_account_id, to_account_id, amount, note))

            # Commit changes to the database
            mysql.connection.commit()
            cur.close()

            flash('Transfer between accounts completed successfully!', 'success')
        except KeyError as e:
            flash(f'Missing required field: {e}', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')

    return redirect(url_for('transfers'))


# Receive Transfer
@app.route('/receive_transfer', methods=['POST'])
def receive_transfer():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        sender_name = request.form['sender_name']
        receiver_name = request.form['receiver_name']
        receiver_place = request.form['receiver_place']
        amount = float(request.form['amount'])
        currency = request.form['currency']
        note = request.form['note']
        branch = request.form['branch']

        cur = mysql.connection.cursor()

        # Deduct amount from branch balance
        cur.execute("UPDATE branches SET balance = balance - %s WHERE name = %s", (amount, branch))

        # Create a journal entry
        cur.execute("INSERT INTO transactions (from_account_id, to_account_id, amount, currency, note) VALUES (%s, %s, %s, %s, %s)",
                    (branch, None, amount, currency, note))

        mysql.connection.commit()
        cur.close()
        flash('Transfer received successfully!', 'success')
    return redirect(url_for('transfers'))


# Exchange Page
@app.route('/exchange')
def exchange():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch currencies for dropdowns
    cur.execute("SELECT * FROM currencies")
    currencies = cur.fetchall()

    # Fetch accounts for dropdowns
    cur.execute("SELECT * FROM accounts")
    accounts = cur.fetchall()

    cur.close()

    return render_template('exchange.html', currencies=currencies, accounts=accounts)


# Process Exchange Transaction
@app.route('/process_exchange', methods=['POST'])
def process_exchange():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        from_currency = request.form['from_currency']
        to_currency = request.form['to_currency']
        amount = float(request.form['amount'])
        exchange_rate = float(request.form['exchange_rate'])
        commission = float(request.form.get('commission', 0))
        payment_method = request.form['payment_method']
        account_id = request.form.get('account_id', None)

        cur = mysql.connection.cursor()

        # Calculate converted amount
        converted_amount = amount * exchange_rate

        # Deduct amount + commission from the from_account
        if payment_method == 'cash':
            cur.execute("SELECT balance FROM accounts WHERE account_name = %s", (f"Cash {from_currency}",))
        elif payment_method == 'account':
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
        else:
            flash('Invalid payment method.', 'error')
            return redirect(url_for('exchange'))

        from_account_balance = cur.fetchone()[0]

        if from_account_balance < (amount + commission):
            flash('Insufficient balance.', 'error')
            return redirect(url_for('exchange'))

        # Deduct amount + commission
        if payment_method == 'cash':
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_name = %s",
                        (amount + commission, f"Cash {from_currency}"))
        else:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s",
                        (amount + commission, account_id))

        # Add converted amount to the to_account
        cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_name = %s",
                    (converted_amount, f"Cash {to_currency}"))

        # Record the transaction
        cur.execute("INSERT INTO transactions (from_account_id, to_account_id, amount, currency, exchange_rate, commission, transaction_type) VALUES (%s, %s, %s, %s, %s, %s, 'exchange')",
                    (account_id if payment_method == 'account' else None, None, amount, from_currency, exchange_rate, commission))

        mysql.connection.commit()
        cur.close()
        flash('Exchange transaction completed successfully!', 'success')
    return redirect(url_for('exchange'))


# Buy Currency
@app.route('/buy_currency', methods=['POST'])
def buy_currency():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        from_currency = request.form['from_currency']
        to_currency = request.form['to_currency']
        amount = float(request.form['amount'])
        exchange_rate = float(request.form['exchange_rate'])
        commission = float(request.form.get('commission', 0))
        payment_method = request.form['payment_method']
        note = request.form.get('note', '')

        cur = mysql.connection.cursor()

        # Calculate converted amount
        converted_amount = amount * exchange_rate

        # Deduct amount + commission from the from_account
        if payment_method == 'cash':
            cur.execute("SELECT balance FROM accounts WHERE account_name = %s", (f"Cash {from_currency}",))
        elif payment_method == 'bank':
            cur.execute("SELECT balance FROM accounts WHERE account_name = %s", (f"Bank {from_currency}",))
        else:
            flash('Invalid payment method.', 'error')
            return redirect(url_for('exchange'))

        from_account_balance = cur.fetchone()[0]

        if from_account_balance < (amount + commission):
            flash('Insufficient balance.', 'error')
            return redirect(url_for('exchange'))

        # Deduct amount + commission
        if payment_method == 'cash':
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_name = %s",
                        (amount + commission, f"Cash {from_currency}"))
        else:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_name = %s",
                        (amount + commission, f"Bank {from_currency}"))

        # Add converted amount to the to_account
        cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_name = %s",
                    (converted_amount, f"Cash {to_currency}"))

        # Record the transaction
        cur.execute("INSERT INTO transactions (from_account_id, to_account_id, amount, currency, exchange_rate, commission, transaction_type, note) VALUES (%s, %s, %s, %s, %s, %s, 'buy', %s)",
                    (None, None, amount, from_currency, exchange_rate, commission, note))

        mysql.connection.commit()
        cur.close()
        flash('Currency bought successfully!', 'success')
    return redirect(url_for('exchange'))


# Sell Currency
@app.route('/sell_currency', methods=['POST'])
def sell_currency():
    if 'user_id' not in session:
        flash('You must be logged in to perform this action.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        from_currency = request.form['from_currency']
        to_currency = request.form['to_currency']
        amount = float(request.form['amount'])
        exchange_rate = float(request.form['exchange_rate'])
        commission = float(request.form.get('commission', 0))
        payment_method = request.form['payment_method']
        note = request.form.get('note', '')

        cur = mysql.connection.cursor()

        # Calculate converted amount
        converted_amount = amount * exchange_rate

        # Deduct amount + commission from the from_account
        if payment_method == 'cash':
            cur.execute("SELECT balance FROM accounts WHERE account_name = %s", (f"Cash {from_currency}",))
        elif payment_method == 'bank':
            cur.execute("SELECT balance FROM accounts WHERE account_name = %s", (f"Bank {from_currency}",))
        else:
            flash('Invalid payment method.', 'error')
            return redirect(url_for('exchange'))

        from_account_balance = cur.fetchone()[0]

        if from_account_balance < (amount + commission):
            flash('Insufficient balance.', 'error')
            return redirect(url_for('exchange'))

        # Deduct amount + commission
        if payment_method == 'cash':
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_name = %s",
                        (amount + commission, f"Cash {from_currency}"))
        else:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE account_name = %s",
                        (amount + commission, f"Bank {from_currency}"))

        # Add converted amount to the to_account
        cur.execute("UPDATE accounts SET balance = balance + %s WHERE account_name = %s",
                    (converted_amount, f"Cash {to_currency}"))

        # Record the transaction
        cur.execute("INSERT INTO transactions (from_account_id, to_account_id, amount, currency, exchange_rate, commission, transaction_type, note) VALUES (%s, %s, %s, %s, %s, %s, 'sell', %s)",
                    (None, None, amount, from_currency, exchange_rate, commission, note))

        mysql.connection.commit()
        cur.close()
        flash('Currency sold successfully!', 'success')
    return redirect(url_for('exchange'))


# Update Company Info (Admin Only)
@app.route('/update_company_info', methods=['POST'])
def update_company_info():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        manager = request.form['manager']
        contact = request.form['contact']
        email = request.form['email']
        logo = request.files['logo']

        # Save the logo file
        logo_url = None
        if logo and logo.filename != '':
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo.filename)
            logo.save(logo_path)
            logo_url = url_for('static', filename=f'uploads/{logo.filename}')

        cur = mysql.connection.cursor()
        if logo_url:
            cur.execute("UPDATE company_info SET name = %s, manager = %s, contact = %s, email = %s, logo = %s WHERE company_id = 1",
                        (name, manager, contact, email, logo_url))
        else:
            cur.execute("UPDATE company_info SET name = %s, manager = %s, contact = %s, email = %s WHERE company_id = 1",
                        (name, manager, contact, email))
        mysql.connection.commit()
        cur.close()
        flash('Company information updated successfully!', 'success')
    return redirect(url_for('settings'))


# Add User (Admin Only)
@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (username, password, role))
        mysql.connection.commit()
        cur.close()
        flash('User added successfully!', 'success')
    return redirect(url_for('settings'))


# Settings Page (Admin Only)
@app.route('/settings')
def settings():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM company_info")
    company_info = cur.fetchone()
    cur.execute("SELECT * FROM currencies")
    currencies = cur.fetchall()
    cur.execute("SELECT * FROM account_types")
    account_types = cur.fetchall()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.close()
    return render_template('settings.html', company_info=company_info, currencies=currencies,
                          account_types=account_types, users=users)


# Reports Page
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Fetch accounts
    cur.execute("SELECT * FROM accounts")
    accounts = cur.fetchall()

    cur.close()

    return render_template('reports.html', accounts=accounts)


# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')


# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)