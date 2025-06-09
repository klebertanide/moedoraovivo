from flask import Flask

app = Flask(__name__ )

@app.route('/')
def home():
    return '''
    <h1>MOEDOR AO VIVO - TESTE</h1>
    <p>Servidor funcionando!</p>
    <p>Se você vê esta página, o Flask está OK.</p>
    '''

if __name__ == '__main__':
    print("Servidor teste rodando em http://localhost:5000" )
    app.run(host='0.0.0.0', port=5000, debug=True)
