# Importações (todas no topo)
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user

from app import app, bcrypt
from app.models import Usuario

# Rotas


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        usuario = Usuario.query.filter_by(email=email).first()

        senha_valida = False
        if usuario:
            try:
                # Primeiro tenta validar como bcrypt
                senha_valida = bcrypt.check_password_hash(usuario.senha, senha)
            except ValueError:
                # Se der erro (senha não é hash bcrypt), compara diretamente
                senha_valida = usuario.senha == senha

        if usuario and senha_valida:
            login_user(usuario)
            session["usuario_nome"] = usuario.nome
            return redirect(url_for("dashboard"))
        else:
            flash("Credenciais inválidas.")
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/pedidos/novo", methods=["GET", "POST"])
@login_required
def novo_pedido():
    if request.method == "POST":
        # lógica para salvar o pedido no banco aqui
        pass
    return render_template("pedidos/novo_pedido.html")


@app.route("/pedido")
def tela_pedido():
    return render_template("pedido.html")
