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
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração de E-mail
EMAIL_CONFIG = {
    "remetente": "cyberdigitalsuporte@gmail.com",
    "senha": "agcwkjbvzgkhowgl",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 465
}

ph = PasswordHasher()

# ================== ROTAS ==================
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        email = data.get("email")
        senha = data.get("senha")

        if not email or not senha:
            return jsonify({"error": "Email e senha são obrigatórios"}), 400

        # Verifica se o e-mail já está cadastrado
        result = supabase.table("usuarios").select("email").eq("email", email).execute()
        if result.data:
            return jsonify({"error": "E-mail já registrado."}), 400

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

    except Exception as e:
        logger.error(f"Erro no registro: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno no servidor."}), 500


@app.route("/webhook/<int:modulo_id>", methods=["POST"])
def liberar_acesso(modulo_id):
    try:
        data = request.get_json()
        email = data.get("contactEmail") or data.get("customer", {}).get("email")

        if not email or "@" not in email:
            return jsonify({"success": False, "message": "Email inválido"}), 400

        corpo_email = f"""
        <!DOCTYPE html>
        <html lang="pt-br">
        <!-- mesmo conteúdo HTML aqui -->
        """

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

        usuario = supabase.table("usuarios").select("*").eq("email", email).execute().data

        if usuario:
            modulos_atuais = usuario[0].get("modulos", [])
            novos_modulos = list(set(modulos_atuais + [modulo_id]))
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
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "message": "Email necessário"}), 400

        resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()

        if not resultado.data:
            return jsonify({"success": False, "message": "Usuário não encontrado"}), 404

        return jsonify({"success": True, "modulos": resultado.data[0]["modulos"]}), 200

    except Exception as e:
        logger.error(f"Erro ao listar módulos: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Erro ao buscar módulos"}), 500

if __name__ == "__main__":
    try:
        socket.gethostbyname(EMAIL_CONFIG["smtp_server"])
        logger.info("Conexão SMTP verificada")
    except socket.error as e:
        logger.error(f"Erro de DNS: {str(e)}")

    app.run(host="0.0.0.0", port=10000, debug=False)
