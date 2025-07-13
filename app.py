from flask 
import Flask, request, jsonify, make_response from supabase import create_client, Client from flask_cors import CORS import yagmail from argon2 import PasswordHasher, exceptions as argon2_exceptions import logging import traceback import socket import secrets

=== CONFIGURAÇÕES GERAIS ===

logging.basicConfig(level=logging.DEBUG) logger = logging.getLogger("CyberDigitalAPI")

app = Flask(name) CORS(app, resources={r"/": {"origins": ""}})

=== Supabase ===

SUPABASE_URL = "https://szbptsuvjmaqkcgsgagx.supabase.co" SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN6YnB0c3V2am1hcWtjZ3NnYWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxNjA3MjEsImV4cCI6MjA1OTczNjcyMX0.wqjSCJ8evNog5AnP2dzk1t2nkn31EfvqDuaAkXDiqNo" supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

=== E-mail ===

EMAIL_CONFIG = { "remetente": "cyberdigitalsuporte@gmail.com", "senha": "agcwkjbvzgkhowgl", "smtp_server": "smtp.gmail.com", "smtp_port": 465 }

ph = PasswordHasher()

def resposta_json(data, status=200): resp = make_response(jsonify(data), status) resp.headers["Access-Control-Allow-Origin"] = "*" resp.headers["Access-Control-Allow-Headers"] = "Content-Type" return resp

@app.route("/register", methods=["POST"]) def register(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower() senha = data.get("senha", "").strip()

if not email or not senha:
        return resposta_json({"success": False, "message": "Email e senha são obrigatórios"}, 400)

    result = supabase.table("usuarios").select("*").eq("email", email).execute()

    if result.data:
        usuario = result.data[0]
        if usuario.get("pagamento_confirmado"):
            senha_hash = ph.hash(senha)
            supabase.table("usuarios").update({
                "senha": senha_hash,
                "nome": data.get("nome", "Usuário Atualizado")
            }).eq("email", email).execute()
            return resposta_json({"success": True, "message": "Senha atualizada com sucesso."})
        else:
            return resposta_json({"success": False, "message": "E-mail já registrado, mas ainda não confirmado."}, 400)

    senha_hash = ph.hash(senha)
    insert = supabase.table("usuarios").insert({
        "email": email,
        "senha": senha_hash,
        "nome": data.get("nome", "Novo Usuário"),
        "modulos": [],
        "pagamento_confirmado": False
    }).execute()

    if insert.data:
        return resposta_json({"success": True, "message": "Cadastro realizado com sucesso."}, 201)
    return resposta_json({"success": False, "message": "Erro ao cadastrar usuário."}, 500)

except Exception:
    logger.error("Erro no registro:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

@app.route("/login", methods=["POST"]) def login(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower() senha = data.get("senha", "").strip()

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
        "message": "Login bem-sucedido",
        "usuario": {
            "email": usuario["email"],
            "modulos": usuario.get("modulos", []),
            "nome": usuario.get("nome", "Usuário")
        }
    })

except Exception:
    logger.error("Erro no login:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

@app.route("/webhook", methods=["POST"]) def liberar_acesso(): try: data = request.get_json(force=True) email = (data.get("contactEmail") or data.get("customer", {}).get("email", "")).strip().lower() modulos_ids = data.get("modulos", [])

if not email or "@" not in email:
        return resposta_json({"success": False, "message": "Email inválido."}, 400)

    if not isinstance(modulos_ids, list) or not all(isinstance(m, int) for m in modulos_ids):
        return resposta_json({"success": False, "message": "Lista de módulos inválida."}, 400)

    corpo_email = f"""
    <html><body>
    <h2>🔥 Salve, Visionário!</h2>
    <p>Os seguintes módulos foram liberados:</p>
    <ul>{''.join(f'<li><strong>{m}</strong></li>' for m in modulos_ids)}</ul>
    <a href='https://cyberflux.onrender.com'>Acessar plataforma</a>
    </body></html>
    """

    yag = yagmail.SMTP(
        user=EMAIL_CONFIG["remetente"],
        password=EMAIL_CONFIG["senha"],
        host=EMAIL_CONFIG["smtp_server"],
        port=EMAIL_CONFIG["smtp_port"],
        smtp_ssl=True
    )
    yag.send(to=email, subject="🎉 Acesso Liberado - Cyber.Digital", contents=corpo_email)

    resultado = supabase.table("usuarios").select("*").eq("email", email).execute()
    if resultado.data:
        usuario = resultado.data[0]
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

    return resposta_json({"success": True, "message": "Acesso liberado com sucesso!"})

except Exception:
    logger.error("Erro no webhook:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

@app.route("/modulos", methods=["POST"]) def listar_modulos(): try: data = request.get_json(force=True) email = data.get("email", "").strip().lower()

if not email:
        return resposta_json({"success": False, "message": "Email necessário."}, 400)

    resultado = supabase.table("usuarios").select("modulos").eq("email", email).execute()
    if not resultado.data:
        return resposta_json({"success": False, "message": "Usuário não encontrado."}, 404)

    return resposta_json({"success": True, "modulos": resultado.data[0].get("modulos", [])})

except Exception:
    logger.error("Erro ao listar módulos:\n" + traceback.format_exc())
    return resposta_json({"success": False, "message": "Erro ao buscar módulos."}, 500)

@app.route("/ping", methods=["GET"]) def ping(): try: return resposta_json({"success": True, "message": "Servidor funcionando."}) except Exception: logger.error("Erro no ping:\n" + traceback.format_exc()) return resposta_json({"success": False, "message": "Erro interno no servidor."}, 500)

if name == "main": try: socket.gethostbyname(EMAIL_CONFIG["smtp_server"]) logger.info("Conexão SMTP verificada") except socket.error as e: logger.error(f"Erro de DNS: {str(e)}")

app.run(host="0.0.0.0", port=10000)



