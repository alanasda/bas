from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from supabase import create_client, Client
from argon2 import PasswordHasher, exceptions as argon2_exceptions
import yagmail
import logging
import traceback
import secrets

# === LOGGING ===
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("CyberDigitalAPI")

# === FLASK + CORS ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# === SUPABASE CONFIG ===
SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN6YnB0c3V2am1hcWtjZ3NnYWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNjA3MjEsImV4cCI6MjA1OTczNjcyMX0.wqjSCJ8evNog5AnP2dzk1t2nkn31EfvqDuaAkXDiqNo"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === E-MAIL CONFIG (GMAIL) ===
EMAIL_CONFIG = {
    "remetente": "cyberdigitalsuporte@gmail.com",
    "senha": "agcwkjbvzgkhowgl",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 465
}

ph = PasswordHasher()

# === RESPOSTA PADRÃO ===
def resposta_json(data, status=200):
    resp = make_response(jsonify(data), status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

# === REGISTRO ===
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True) or {}
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return resposta_json({"error": "Email e senha são obrigatórios"}, 400)

        result = supabase.table("usuarios").select("*").eq("email", email).execute()

        if not result or not result.data:
            senha_hash = ph.hash(senha)
            insert = supabase.table("usuarios").insert({
                "email": email,
                "senha": senha_hash,
                "nome": "Novo Usuário",
                "modulos": [],
                "pagamento_confirmado": False
            }).execute()

            if not insert or not insert.data:
                logger.error(f"Erro ao inserir usuário: {insert}")
                return resposta_json({"error": "Erro ao cadastrar usuário"}, 500)

            return resposta_json({"message": "Cadastro realizado com sucesso."}, 201)

        usuario = result.data[0]
        if usuario.get("pagamento_confirmado"):
            senha_hash = ph.hash(senha)
            supabase.table("usuarios").update({
                "senha": senha_hash,
                "nome": "Usuário Atualizado"
            }).eq("email", email).execute()
            return resposta_json({"message": "Senha atualizada com sucesso."})

        return resposta_json({"error": "E-mail já registrado."}, 400)

    except Exception:
        logger.error(f"Erro no registro: {traceback.format_exc()}")
        return resposta_json({"error": "Erro interno no servidor"}, 500)

# === LOGIN ===
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True) or {}
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return resposta_json({"error": "Email e senha obrigatórios"}, 400)

        result = supabase.table("usuarios").select("*").eq("email", email).execute()
        if not result or not result.data:
            return resposta_json({"error": "Usuário não encontrado"}, 404)

        usuario = result.data[0]

        try:
            ph.verify(usuario["senha"], senha)
        except argon2_exceptions.VerifyMismatchError:
            return resposta_json({"error": "Senha incorreta"}, 401)

        return resposta_json({
            "success": True,
            "message": "Login bem-sucedido",
            "usuario": {
                "email": usuario["email"],
                "nome": usuario.get("nome", "Usuário"),
                "modulos": usuario.get("modulos", [])
            }
        })

    except Exception:
        logger.error(f"Erro no login: {traceback.format_exc()}")
        return resposta_json({"error": "Erro interno no servidor"}, 500)

# === WEBHOOK DE LIBERAÇÃO DE MÓDULOS ===
@app.route("/webhook", methods=["POST"])
def liberar_acesso():
    try:
        data = request.get_json(force=True) or {}
        email = data.get("contactEmail") or data.get("customer", {}).get("email")
        modulos_ids = data.get("modulos")

        if not email or "@" not in email:
            return resposta_json({"success": False, "message": "Email inválido"}, 400)

        if not isinstance(modulos_ids, list) or not all(isinstance(m, int) for m in modulos_ids):
            return resposta_json({"success": False, "message": "Lista de módulos inválida"}, 400)

        corpo_email = f"""
        <html><body style="font-family:sans-serif;">
        <div style="background:linear-gradient(45deg,#FFA500,#FFD700);padding:20px;border-radius:10px;">
        <h2>🔥 Salve, Visionário!</h2>
        <p>Os seguintes módulos foram liberados para você:</p>
        <ul>
            {''.join(f'<li><strong>{m}</strong></li>' for m in modulos_ids)}
        </ul>
        <a href='https://cyberflux.onrender.com'>Acessar plataforma</a>
        </div></body></html>
        """

        yag = yagmail.SMTP(
            user=EMAIL_CONFIG["remetente"],
            password=EMAIL_CONFIG["senha"],
            host=EMAIL_CONFIG["smtp_server"],
            port=EMAIL_CONFIG["smtp_port"],
            smtp_ssl=True
        )
        yag.send(to=email, subject="🎉 Acesso Liberado - Cyber.Digital", contents=corpo_email)

        result = supabase.table("usuarios").select("*").eq("email", email).execute()
        usuario_data = result.data if result and result.data else None

        if usuario_data:
            usuario = usuario_data[0]
            modulos_atuais = usuario.get("modulos", [])
            novos_modulos = list(set(modulos_atuais + modulos_ids))
            supabase.table("usuarios").update({
                "modulos": novos_modulos,
                "pagamento_confirmado": True
            }).eq("email", email).execute()
        else:
            senha_temp = secrets.token_hex(4)
            senha_hash = ph.hash(senha_temp)
            supabase.table("usuarios").insert({
                "email": email,
                "nome": "Usuário Webhook",
                "senha": senha_hash,
                "modulos": modulos_ids,
                "pagamento_confirmado": True
            }).execute()

        return resposta_json({"success": True, "message": "Acesso liberado com sucesso!"})

    except yagmail.YagAddressError:
        return resposta_json({"success": False, "message": "Endereço de e-mail inválido"}, 400)
    except Exception:
        logger.error(f"Erro no webhook: {traceback.format_exc()}")
        return resposta_json({"success": False, "message": "Erro interno no servidor"}, 500)

# === MÓDULOS ===
@app.route("/modulos", methods=["POST"])
def listar_modulos():
    try:
        data = request.get_json(force=True) or {}
        email = data.get("email")

        if not email:
            return resposta_json({"success": False, "message": "Email necessário"}, 400)

        resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()

        if not resultado or not resultado.data:
            return resposta_json({"success": False, "message": "Usuário não encontrado"}, 404)

        return resposta_json({"success": True, "modulos": resultado.data[0]["modulos"]})

    except Exception:
        logger.error(f"Erro ao listar módulos: {traceback.format_exc()}")
        return resposta_json({"success": False, "message": "Erro ao buscar módulos"}, 500)

# === PING ===
@app.route("/ping", methods=["GET"])
def ping():
    try:
        return resposta_json({"success": True, "message": "Servidor funcionando"})
    except Exception:
        logger.error(f"Erro no ping: {traceback.format_exc()}")
        return resposta_json({"success": False, "message": "Erro interno no servidor"}, 500)

# === RODAR SERVIDOR ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
