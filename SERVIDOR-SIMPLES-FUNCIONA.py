from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <html>
    <head><title>MOEDOR AO VIVO</title></head>
    <body style="background: black; color: white; font-family: monospace; text-align: center; padding: 50px;">
        <h1 style="color: red; font-size: 3em;">MOEDOR AO VIVO</h1>
        <h2 style="color: green;">✅ FUNCIONANDO!</h2>
        <p>Servidor Flask rodando perfeitamente!</p>
        <p>Porta: 5001</p>
        <p>Status: Online</p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚀 MOEDOR AO VIVO - Servidor funcionando!")
    print("📍 Acesse: http://localhost:5001" )
    app.run(host='0.0.0.0', port=5001, debug=True)
