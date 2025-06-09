from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <h1 style="color: red;">MOEDOR AO VIVO - USUÁRIOS</h1>
    <p>Interface para espectadores da live</p>
    <a href="/admin">Ir para Admin</a>
    '''

@app.route('/admin')
def admin():
    return '''
    <h1 style="color: orange;">PAINEL ADMINISTRATIVO</h1>
    <p>Controles para o streamer</p>
    <a href="/">Voltar para Interface</a>
    '''

if __name__ == '__main__':
    print("🚀 Servidor rodando:")
    print("👥 Usuários: http://localhost:5001/" )
    print("🎛️ Admin: http://localhost:5001/admin" )
    app.run(host='0.0.0.0', port=5001, debug=True)
