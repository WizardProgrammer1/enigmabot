from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from src.user_repository import UserRepository
import asyncio
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecret')
user_repo = UserRepository()

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        code = request.form.get('code')
        if not code or len(code) != 12:
            error = 'Введите корректный 12-значный код.'
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            user = loop.run_until_complete(user_repo.get_user_by_admin_code(code))
            if user:
                session['admin_id'] = user[0]
                session['admin_name'] = user[1]
                session['a_rank'] = user[2]
                return redirect(url_for('dashboard'))
            else:
                error = 'Код не найден или нет прав.'
    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', admin_name=session.get('admin_name'))

if __name__ == '__main__':
    # Можно сменить порт на 8000, если 5001 не работает
    app.run(debug=True, port=5001, host='0.0.0.0') 