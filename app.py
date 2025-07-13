from flask import Flask, request, jsonify, make_response from supabase import create_client, Client from flask_cors import CORS import yagmail from argon2 import PasswordHasher, exceptions as argon2_exceptions import logging import traceback import socket import secrets

=== CONFIGURAÇÕES GERAIS ===

logging.basicConfig(level=logging.DEBUG) logger = logging.getLogger("CyberDigitalAPI")

app = Flask(name) CORS(app, resources={r"/": {"origins": ""}})

=== Supabase ===

SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co" SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFz..."  # CHAVE TRUNCADA POR SEGURANÇA supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

=== E-mail ===

EMAIL_CONFIG = { "remetente": "cyberdigitalsuporte@gmail.com", "senha": "agcwkjbvzgkhowgl", "smtp_server": "smtp.gmail.com", "smtp_port": 465 }

ph = PasswordHasher()

def resposta_json(data, status=200): resp = make_response(jsonify(data), status) resp.headers["Access-Control-Allow-Origin"] = "*" resp.headers["Access-Control-Allow-Headers"] = "Content-Type" return resp

=== LOGIN ===

@app.route("/login", methods=["POST"]) def login(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower() senha = data.get("senha")

if not email or not senha:
        return resposta_json({"success": False, "message": "Email e senha obrigatórios."}, 400)

    result = supabase.table("usuarios").select("*").eq("email", email).execute()

    if not result.data:
        return resposta_json({"success": False, "message": "Usuário não encontrado."}, 404)

    usuario = result.data[0]

    try:
        ph.verify(usuario["senha"], senha)
    except argon2_exceptions.VerifyMismatchError:
        return resposta_json({"success": False, "message": "Senha incorreta."}, 401)

    return resposta_json({
        "success": True,
        "message": "Login realizado com sucesso.",
        "usuario": {
            "email": usuario.get("email"),
            "modulos": usuario.get("modulos", []),
            "nome": usuario.get("nome", "Usuário")
        }
    })

except Exception:
    logger.error("Erro interno no login:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

=== REGISTRO ===

@app.route("/register", methods=["POST"]) def register(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower() senha = data.get("senha")

if not email or not senha:
        return resposta_json({"success": False, "message": "Email e senha obrigatórios."}, 400)

    result = supabase.table("usuarios").select("*").eq("email", email).execute()

    if result.data:
        usuario = result.data[0]
        if usuario.get("pagamento_confirmado"):
            senha_hash = ph.hash(senha)
            supabase.table("usuarios").update({
                "senha": senha_hash,
                "nome": "Usuário Atualizado"
            }).eq("email", email).execute()
            return resposta_json({"success": True, "message": "Senha atualizada com sucesso."})
        else:
            return resposta_json({"success": False, "message": "Email já registrado."}, 400)
    else:
        senha_hash = ph.hash(senha)
        insert = supabase.table("usuarios").insert({
            "email": email,
            "senha": senha_hash,
            "nome": "Novo Usuário",
            "modulos": [],
            "pagamento_confirmado": False
        }).execute()

        if insert.data:
            return resposta_json({"success": True, "message": "Cadastro realizado com sucesso."}, 201)
        else:
            return resposta_json({"success": False, "message": "Erro ao cadastrar usuário."}, 500)

except Exception:
    logger.error("Erro interno no registro:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

=== MÓDULOS ===

@app.route("/modulos", methods=["POST"]) def listar_modulos(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower()

if not email:
        return resposta_json({"success": False, "message": "Email obrigatório."}, 400)

    resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()

    if not resultado.data:
        return resposta_json({"success": False, "message": "Usuário não encontrado."}, 404)

    return resposta_json({"success": True, "modulos": resultado.data[0]["modulos"]})

except Exception:
    logger.error("Erro ao listar módulos:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro ao buscar módulos."}, 500)

=== WEBHOOK ===

@app.route("/webhook", methods=["POST"]) def liberar_acesso(): try: data = request.get_json(force=True) email = data.get("contactEmail") or data.get("customer", {}).get("email") modulos_ids = data.get("modulos")

if not email or not isinstance(modulos_ids, list):
        return resposta_json({"success": False, "message": "Dados inválidos."}, 400)

    yag = yagmail.SMTP(
        user=EMAIL_CONFIG["remetente"],
        password=EMAIL_CONFIG["senha"],
        host=EMAIL_CONFIG["smtp_server"],
        port=EMAIL_CONFIG["smtp_port"],
        smtp_ssl=True
    )

    yag.send(
        to=email,
        subject="Cyber.Digital - Acesso Liberado",
        contents=f"Você recebeu acesso aos módulos: {modulos_ids}"
    )

    usuario_result = supabase.table("usuarios").select("*").eq("email", email).execute()

    if usuario_result.data:
        usuario = usuario_result.data[0]
        modulos_atuais = usuario.get("modulos", [])
        novos_modulos = list(set(modulos_atuais + modulos_ids))
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
            "modulos": modulos_ids,
            "pagamento_confirmado": True
        }).execute()

    return resposta_json({"success": True, "message": "Acesso liberado."})

except Exception:
    logger.error("Erro no webhook:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno."}, 500)

=== PING ===

@app.route("/ping", methods=["GET"]) def ping(): return resposta_json({"success": True, "message": "Servidor funcionando"})

=== MAIN ===

if name == "main": try: socket.gethostbyname(EMAIL_CONFIG["smtp_server"]) logger.info("Conexão SMTP verificada") except socket.error as e: logger.error(f"Erro de DNS SMTP: {str(e)}")

app.run(host="0.0.0.0", port=10000)


