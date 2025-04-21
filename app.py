from flask import Flask, request, jsonify
from supabase import create_client, Client
from flask_cors import CORS
import yagmail
from argon2 import PasswordHasher, exceptions as argon2_exceptions
import logging
import traceback
import socket
import secrets

# === CONFIGURAÇÕES GERAIS ===
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("CyberDigitalAPI")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# === Supabase ===
SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === E-mail ===
EMAIL_CONFIG = {
    "remetente": "cyberdigitalsuporte@gmail.com",
    "senha": "agcwkjbvzgkhowgl",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 465
}

ph = PasswordHasher()

# === ROTA DE REGISTRO COM SUPORTE A CONTA PRÉ-CRIADA PELO WEBHOOK ===
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return jsonify({"error": "Email e senha são obrigatórios"}), 400

        result = supabase.table("usuarios").select("*").eq("email", email).execute()

        if result.data:
            usuario = result.data[0]

            # Se usuário já existe, mas foi criado pelo webhook → permitir atualizar senha
            if usuario["pagamento_confirmado"]:
                senha_hash = ph.hash(senha)
                supabase.table("usuarios").update({
                    "senha": senha_hash,
                    "nome": "Usuário Atualizado"
                }).eq("email", email).execute()
                return jsonify({"message": "Senha atualizada com sucesso."}), 200
            else:
                return jsonify({"error": "E-mail já registrado."}), 400

        # Novo usuário
        senha_hash = ph.hash(senha)
        insert = supabase.table("usuarios").insert({
            "email": email,
            "senha": senha_hash,
            "nome": "Novo Usuário",
            "modulos": [],
            "pagamento_confirmado": False
        }).execute()

        if insert.data:
            return jsonify({"message": "Cadastro realizado com sucesso."}), 201
        else:
            return jsonify({"error": "Erro ao cadastrar usuário."}), 500

    except Exception:
        logger.error(f"Erro no registro: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno no servidor."}), 500

# === ROTA DE WEBHOOK PARA LIBERAR MÓDULO ===
@app.route("/webhook/<int:modulo_id>", methods=["POST"])
def liberar_acesso(modulo_id):
    try:
        data = request.get_json()
        email = data.get("contactEmail") or data.get("customer", {}).get("email")

        if not email or "@" not in email:
            return jsonify({"success": False, "message": "Email inválido"}), 400

        # Corpo do e-mail estilizado
        corpo_email = f"""
        <!DOCTYPE html>
        <html lang="pt-br">
        <head><meta charset="UTF-8"><title>Acesso Liberado</title></head>
        <body style="font-family:sans-serif;padding:20px;background:#fff;">
            <div style="max-width:600px;margin:auto;border-radius:10px;background:linear-gradient(45deg,#FFA500,#FFD700);color:#000;padding:20px;">
                <h2>🔥 Salve, Visionário!</h2>
                <p>Parabéns pelo primeiro passo rumo à sua evolução digital com a <strong>Cyber.Digital</strong>.</p>
                <p>O módulo <strong>{modulo_id}</strong> já está disponível para você acessar.</p>
                <p style="margin-top:20px;">➡️ Acesse agora mesmo: <br><strong>https://seudominio.com/login</strong></p>
                <p style="margin-top:30px;font-style:italic;">Qualquer dúvida, chame a equipe no <strong>@cyberdigital</strong>. Estamos aqui pra você! 🚀</p>
            </div>
        </body>
        </html>
        """

        # Enviar o e-mail
        yag = yagmail.SMTP(
            user=EMAIL_CONFIG["remetente"],
            password=EMAIL_CONFIG["senha"],
            host=EMAIL_CONFIG["smtp_server"],
            port=EMAIL_CONFIG["smtp_port"],
            smtp_ssl=True
        )
        yag.send(to=email, subject="🎉 Acesso Liberado - Cyber.Digital", contents=corpo_email)

        # Buscar ou criar usuário
        usuario = supabase.table("usuarios").select("*").eq("email", email).execute().data

        if usuario:
            modulos_atuais = usuario[0].get("modulos", [])
            novos_modulos = list(set(modulos_atuais + [modulo_id]))
            supabase.table("usuarios").update({
                "modulos": novos_modulos,
                "pagamento_confirmado": True
            }).eq("email", email).execute()
        else:
            senha_temporaria = secrets.token_hex(4)
            senha_hash = ph.hash(senha_temporaria)
            supabase.table("usuarios").insert({
                "email": email,
                "nome": "Usuário Webhook",
                "senha": senha_hash,
                "modulos": [modulo_id],
                "pagamento_confirmado": True
            }).execute()

        return jsonify({"success": True, "message": "Acesso liberado com sucesso!"}), 200

    except yagmail.YagAddressError:
        return jsonify({"success": False, "message": "Endereço de e-mail inválido"}), 400
    except Exception:
        logger.error(f"Erro no webhook: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro interno no servidor."}), 500

# === ROTA PARA CONSULTAR MÓDULOS DO USUÁRIO ===
@app.route("/modulos", methods=["POST"])
def listar_modulos():
    try:
        data = request.get_json()
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "message": "Email necessário"}), 400

        resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()

        if not resultado.data:
            return jsonify({"success": False, "message": "Usuário não encontrado"}), 404

        return jsonify({"success": True, "modulos": resultado.data[0]["modulos"]}), 200

    except Exception:
        logger.error(f"Erro ao listar módulos: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro ao buscar módulos"}), 500

# === ROTA DE PING PARA UPTIMEROBOT ===
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"}), 200

# === VERIFICA SMTP NO INÍCIO ===
if __name__ == "__main__":
    try:
        socket.gethostbyname(EMAIL_CONFIG["smtp_server"])
        logger.info("Conexão SMTP verificada")
    except socket.error as e:
        logger.error(f"Erro de DNS: {str(e)}")

    app.run(host="0.0.0.0", port=10000, debug=False)
