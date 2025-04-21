from flask import Flask, request, jsonify
from supabase import create_client, Client
from flask_cors import CORS
import yagmail
from argon2 import PasswordHasher, exceptions as argon2_exceptions
import logging
import traceback
import socket

# Configurações básicas
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("CyberDigitalAPI")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuração Supabase
SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN6YnB0c3V2am1hcWtjZ3NnYWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNjA3MjEsImV4cCI6MjA1OTczNjcyMX0.wqjSCJ8evNog5AnP2dzk1t2nkn31EfvqDuaAkXDiqNo"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração de E-mail
EMAIL_CONFIG = {
    "remetente": "cyberdigitalsuporte@gmail.com",
    "senha": "agcwkjbvzgkhowgl",  # Senha sem espaços
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 465
}

# Inicializações
ph = PasswordHasher()

# ================== ROTAS PRINCIPAIS ==================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "version": "2.0.0"})

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        required_fields = ["nome", "email", "senha"]
        
        if not all(field in data for field in required_fields):
            return jsonify({"success": False, "message": "Campos obrigatórios faltando"}), 400

        # Verificar se o usuário já existe
        user_exists = supabase.table("usuarios").select("email").eq("email", data["email"]).execute()
        if user_exists.data:
            return jsonify({"success": False, "message": "Email já cadastrado"}), 409

        # Criar novo usuário
        novo_usuario = {
            "nome": data["nome"],
            "email": data["email"],
            "senha": ph.hash(data["senha"]),
            "modulos": [],
            "pagamento_confirmado": False
        }

        supabase.table("usuarios").insert(novo_usuario).execute()
        return jsonify({"success": True, "message": "Usuário registrado com sucesso"}), 201

    except Exception as e:
        logger.error(f"Erro no registro: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro interno no servidor"}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if "email" not in data or "senha" not in data:
            return jsonify({"success": False, "message": "Credenciais necessárias"}), 400

        # Buscar usuário
        result = supabase.table("usuarios").select("*").eq("email", data["email"]).execute()
        if not result.data:
            return jsonify({"success": False, "message": "Credenciais inválidas"}), 401

        usuario = result.data[0]

        # Verificar senha
        try:
            ph.verify(usuario["senha"], data["senha"])
        except argon2_exceptions.VerifyMismatchError:
            return jsonify({"success": False, "message": "Credenciais inválidas"}), 401

        return jsonify({
            "success": True,
            "usuario": {
                "email": usuario["email"],
                "nome": usuario["nome"],
                "modulos": usuario["modulos"]
            }
        }), 200

    except Exception as e:
        logger.error(f"Erro no login: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro de autenticação"}), 500

@app.route("/webhook/<int:modulo_id>", methods=["POST"])
def liberar_acesso(modulo_id):
    try:
        data = request.get_json()
        email = data.get("email")

        if not email or "@" not in email:
            return jsonify({"success": False, "message": "Email inválido"}), 400

        # Template de E-mail Profissional
        corpo_email = f"""
       <!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acesso Liberado - Módulo Profissional</title>
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f7f7f7;
        }}
        .header {{
            background: linear-gradient(135deg, #FF6B00, #FFA726);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .content {{
            padding: 30px;
            background-color: white;
            color: #333;
        }}
        .cta-button {{
            display: inline-block;
            padding: 15px 30px;
            background-color: #FF6B00;
            color: white;
            text-decoration: none;
            font-weight: bold;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .footer {{
            background-color: #f1f1f1;
            padding: 15px;
            text-align: center;
            font-size: 12px;
            color: #777;
        }}
    </style>
</head>
<body>

    <div class="header">
        <h1>🚀 CyberDigital Mentoria</h1>
    </div>

    <div class="content">
        <h2>Parabéns, Visionário!</h2>
        <p>Seu acesso ao <strong>Módulo {modulo_id}</strong> foi liberado com sucesso!</p>
        <p>Prepare-se para dar um grande passo na sua jornada de transformação digital.</p>

        <center>
            <a href="https://cyberflux.onrender.com" class="cta-button">
                Acessar Plataforma →
            </a>
        </center>

        <p><strong>Precisa de ajuda?</strong><br>
        Entre em contato conosco a qualquer momento: <a href="mailto:{EMAIL_CONFIG['remetente']}">{EMAIL_CONFIG['remetente']}</a></p>
    </div>

    <div class="footer">
        <p>© 2024 CyberDigital - Todos os direitos reservados</p>
    </div>

</body>
</html>

        """

        # Enviar e-mail
        yag = yagmail.SMTP(
            user=EMAIL_CONFIG["remetente"],
            password=EMAIL_CONFIG["senha"],
            host=EMAIL_CONFIG["smtp_server"],
            port=EMAIL_CONFIG["smtp_port"],
            smtp_ssl=True
        )
        yag.send(
            to=email,
            subject=f"🎉 Acesso Liberado - Módulo {modulo_id}",
            contents=corpo_email
        )

        # Atualizar banco de dados
        usuario = supabase.table("usuarios").select("*").eq("email", email).execute().data
        if usuario:
            novos_modulos = list(set(usuario[0]["modulos"] + [modulo_id]))
            supabase.table("usuarios").update({"modulos": novos_modulos}).eq("email", email).execute()
        else:
            supabase.table("usuarios").insert({
                "email": email,
                "nome": "Novo Usuário",
                "senha": ph.hash("temp_password"),
                "modulos": [modulo_id],
                "pagamento_confirmado": True
            }).execute()

        return jsonify({"success": True, "message": "Acesso liberado com sucesso!"}), 200

    except yagmail.YagAddressError:
        return jsonify({"success": False, "message": "Endereço de e-mail inválido"}), 400
    except Exception as e:
        logger.error(f"Erro no webhook: {traceback.format_exc()}")
        return jsonify({"success": False, "message": f"Erro: {str(e)}"}), 500

@app.route("/modulos", methods=["POST"])
def listar_modulos():
    try:
        data = request.get_json()
        if "email" not in data:
            return jsonify({"success": False, "message": "Email necessário"}), 400

        resultado = supabase.table("usuarios").select("modulos").eq("email", data["email"]).execute()
        if not resultado.data:
            return jsonify({"success": False, "message": "Usuário não encontrado"}), 404

        return jsonify({"success": True, "modulos": resultado.data[0]["modulos"]}), 200

    except Exception as e:
        logger.error(f"Erro ao listar módulos: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro ao buscar módulos"}), 500

if __name__ == "__main__":
    # Verificação de conexão ao iniciar
    try:
        socket.gethostbyname(EMAIL_CONFIG["smtp_server"])
        logger.info("Conexão SMTP verificada")
    except socket.error as e:
        logger.error(f"Erro de DNS: {str(e)}")

    app.run(host="0.0.0.0", port=10000, debug=False)
