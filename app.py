from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from supabase import create_client, Client
from argon2 import PasswordHasher, exceptions as argon2_exceptions
import yagmail
import secrets
import logging
import traceback

# === CONFIGURAÇÕES GERAIS ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("CyberDigitalAPI")

# === SUPABASE CONFIG ===
SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN6YnB0c3V2am1hcWtjZ3NnYWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNjA3MjEsImV4cCI6MjA1OTczNjcyMX0.wqjSCJ8evNog5AnP2dzk1t2nkn31EfvqDuaAkXDiqNo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === E-MAIL CONFIG (GMAIL) ===
EMAIL = "cyberdigitalsuporte@gmail.com"
EMAIL_SENHA = "agcwkjbvzgkhowgl"

# === SENHAS ===
ph = PasswordHasher()

# === FUNÇÃO PADRÃO DE RESPOSTA JSON ===
def resposta(data, status=200):
    resp = make_response(jsonify(data), status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

# === ROTA DE REGISTRO ===
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return resposta({"error": "Email e senha são obrigatórios"}, 400)

        resultado = supabase.table("usuarios").select("*").eq("email", email).execute()

        if resultado.data:
            usuario = resultado.data[0]
            if usuario.get("pagamento_confirmado"):
                nova_senha = ph.hash(senha)
                supabase.table("usuarios").update({
                    "senha": nova_senha,
                    "nome": "Usuário Atualizado"
                }).eq("email", email).execute()
                return resposta({"message": "Senha atualizada com sucesso."})
            return resposta({"error": "E-mail já registrado."}, 400)

        senha_hash = ph.hash(senha)
        supabase.table("usuarios").insert({
            "email": email,
            "senha": senha_hash,
            "nome": "Novo Usuário",
            "modulos": [],
            "pagamento_confirmado": False
        }).execute()
        return resposta({"message": "Cadastro realizado com sucesso."}, 201)

    except Exception as e:
        logger.error(traceback.format_exc())
        return resposta({"error": "Erro interno no servidor."}, 500)

# === ROTA DE LOGIN ===
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return resposta({"error": "Email e senha obrigatórios"}, 400)

        resultado = supabase.table("usuarios").select("*").eq("email", email).execute()
        if not resultado.data:
            return resposta({"error": "Usuário não encontrado"}, 404)

        usuario = resultado.data[0]

        try:
            ph.verify(usuario["senha"], senha)
        except argon2_exceptions.VerifyMismatchError:
            return resposta({"error": "Senha incorreta"}, 401)

        return resposta({
            "success": True,
            "message": "Login bem-sucedido",
            "usuario": {
                "email": usuario["email"],
                "nome": usuario.get("nome", "Usuário"),
                "modulos": usuario.get("modulos", [])
            }
        })

    except Exception:
        logger.error(traceback.format_exc())
        return resposta({"error": "Erro interno no servidor"}, 500)

# === ROTA DE LIBERAÇÃO DE MÓDULOS (WEBHOOK) ===
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        email = data.get("contactEmail") or data.get("customer", {}).get("email")
        modulos = data.get("modulos")

        if not email or not modulos:
            return resposta({"success": False, "message": "Dados inválidos"}, 400)

        # Envio de e-mail
        html = f"""
        <html><body style="font-family:sans-serif;">
        <h2>🔥 Salve, Visionário!</h2>
        <p>Você recebeu acesso aos módulos:</p>
        <ul>{''.join(f"<li>{m}</li>" for m in modulos)}</ul>
        <a href="https://cyberflux.onrender.com">Acessar Plataforma</a>
        </body></html>
        """
        yag = yagmail.SMTP(EMAIL, EMAIL_SENHA)
        yag.send(to=email, subject="🎉 Acesso Liberado - Cyber.Digital", contents=html)

        # Atualização no Supabase
        user = supabase.table("usuarios").select("*").eq("email", email).execute().data
        if user:
            existentes = user[0].get("modulos", [])
            atualizados = list(set(existentes + modulos))
            supabase.table("usuarios").update({
                "modulos": atualizados,
                "pagamento_confirmado": True
            }).eq("email", email).execute()
        else:
            senha_temp = ph.hash(secrets.token_hex(4))
            supabase.table("usuarios").insert({
                "email": email,
                "nome": "Usuário Webhook",
                "senha": senha_temp,
                "modulos": modulos,
                "pagamento_confirmado": True
            }).execute()

        return resposta({"success": True, "message": "Módulos liberados com sucesso!"})

    except Exception:
        logger.error(traceback.format_exc())
        return resposta({"success": False, "message": "Erro interno no servidor"}, 500)

# === ROTA PARA LISTAR MÓDULOS ===
@app.route("/modulos", methods=["POST"])
def listar_modulos():
    try:
        email = request.get_json(force=True).get("email")
        if not email:
            return resposta({"success": False, "message": "Email obrigatório"}, 400)

        resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()
        if not resultado.data:
            return resposta({"success": False, "message": "Usuário não encontrado"}, 404)

        return resposta({"success": True, "modulos": resultado.data[0]["modulos"]})

    except Exception:
        logger.error(traceback.format_exc())
        return resposta({"success": False, "message": "Erro ao buscar módulos"}, 500)

# === ROTA DE TESTE (PING) ===
@app.route("/ping", methods=["GET"])
def ping():
    return resposta({"success": True, "message": "Servidor no ar!"})

# === INICIAR SERVIDOR ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
