#!/usr/bin/env python3
"""
Micro-app Flask: Login mínimo e redirecionamento
"""

import os
from datetime import timedelta
from flask import Flask, request, session, redirect, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-por-uma-chave-secreta')
app.permanent_session_lifetime = timedelta(days=30)

# Lista de emails autorizados (local)
AUTHORIZED_EMAILS = {
    'admin@moedor.com',
    'teste@moedor.com'
}

# URL de destino após login bem-sucedido
REDIRECT_URL = os.environ.get('REDIRECT_URL', 'http://localhost:5002/')

# Template HTML simples para login
LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Login MOEDOR</title>
  <style>
    body { font-family: sans-serif; background: #f5f5f5; display: flex; height: 100vh; align-items: center; justify-content: center; }
    .box { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
    input, button { width: 100%; padding: 0.5rem; margin: 0.5rem 0; }
    .error { color: red; }
  </style>
</head>
<body>
  <div class="box">
    <h2>Faça login</h2>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form method="POST">
      <input type="email" name="email" placeholder="Email de compra" required autocapitalize="none">
      <button type="submit">Entrar</button>
    </form>
  </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if email in AUTHORIZED_EMAILS:
            session['email'] = email
            session.permanent = True
            return redirect(REDIRECT_URL)
        return render_template_string(LOGIN_HTML, error='Email não autorizado')
    return render_template_string(LOGIN_HTML, error=None)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
